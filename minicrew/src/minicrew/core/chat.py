"""1:1 conversation with a single agent, optionally grounded in project knowledge.

Stateless: the caller keeps the history and passes it in each turn. The agent's
persona is the system prompt; with `ground=True` the relevant pitfalls + top-k
literature for the message are injected (same trust-tiered knowledge the crews
use). Distinct from a crew: this is a brainstorm with one expert, not a panel.
"""
from __future__ import annotations

import datetime
import glob
import json
import os

from . import config, knowledge, llm


def reply(agent, history, message, ground=False, max_tokens=1500):
    """agent: {name, model, body}; history: [{role, content}, …] (prior turns)."""
    system = agent.get("body") or "You are a helpful, rigorous research expert."
    parts = []
    if ground:
        kn = knowledge.build(["pitfalls", "literature"], query=message)
        if kn:
            parts.append("## Project knowledge — weigh by TRUST tier\n" + kn)
    convo = "\n\n".join(
        f"{'User' if h['role'] == 'user' else agent.get('name', 'You')}: {h['content']}"
        for h in history)
    if convo:
        parts.append("## Conversation so far\n" + convo)
    parts.append("## User\n" + message)
    spec = config.resolve_model(agent.get("model") or "claude_cli")
    return llm.call(spec, system, "\n\n".join(parts), max_tokens=max_tokens)


def _slug(name):
    return name.lower().replace("/", "-").replace(" ", "_")


def list_saved_chats(limit=50):
    """Newest-first saved chats: [(label, json_path, agent_name)].

    Sorted by file mtime (not filename — filenames start with the agent slug, so
    a name sort would not be chronological).
    """
    out = []
    paths = sorted(glob.glob(os.path.join(config.RUNS_DIR, "chat_*.json")),
                   key=os.path.getmtime, reverse=True)
    for p in paths[:limit]:
        try:
            r = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if r.get("kind") != "chat":
            continue
        topic = (r.get("task", "") or "")[:40]
        label = f"{r.get('agent', '?')} · {r.get('timestamp', '?')} · {topic}"
        out.append((label, p, r.get("agent", "")))
    return out


def load_history(json_path):
    """Reconstruct [{role, content}] history (+ agent name) from a saved chat."""
    r = json.load(open(json_path, encoding="utf-8"))
    hist = [{"role": "user" if o.get("agent") == "You" else "assistant",
             "content": o.get("reply", "")} for o in r.get("outputs", [])]
    return hist, r.get("agent", "")


def save_session(agent, history, task=None):
    """Persist a 1:1 chat to conversations/ (human md) + runs/ (json record).

    The json record uses the SAME shape as a crew run
    ({run_id, crew, task, outputs:[{agent, alias, reply, ok}]}) plus
    ``kind: "chat"``, so it can be sedimented later — but routed to an
    *engineering* note rather than a strategic *decisions* note (chat captures how
    things were built / what technical route changed, not plan-level consensus).
    Returns (md_path, json_path).
    """
    name = agent.get("name", "agent")
    model = agent.get("model", "")
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _slug(name)
    task = task or (history[0]["content"][:80] if history else "1:1 chat")

    # human-readable transcript
    lines = [f"# Chat — {name}", f"_{ts} · model `{model}`_", ""]
    for h in history:
        who = "You" if h["role"] == "user" else name
        lines.append(f"**{who}:**\n\n{h['content']}\n")
    os.makedirs(config.CONV_DIR, exist_ok=True)
    md_path = os.path.join(config.CONV_DIR, f"chat_{slug}_{ts}.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    # sediment-compatible record (outputs read by scribe._transcript_text)
    outputs = [{"agent": "You" if h["role"] == "user" else name,
                "alias": "" if h["role"] == "user" else model,
                "reply": h["content"], "ok": True} for h in history]
    record = {"run_id": ts, "crew": f"chat:{slug}", "kind": "chat",
              "timestamp": ts, "task": task, "agent": name, "model": model,
              "outputs": outputs}
    os.makedirs(config.RUNS_DIR, exist_ok=True)
    json_path = os.path.join(config.RUNS_DIR, f"chat_{slug}_{ts}.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, ensure_ascii=False)
    return md_path, json_path


_ESCALATE_SYS = """\
You are preparing to ESCALATE a 1:1 engineering chat to a multi-expert review
panel, because a technical-route decision has surfaced that deserves several
independent perspectives. From the transcript (only), produce a tight brief:

# <the single decision question — one sentence, the fork that needs deciding>

## Context for the panel
- what's been tried / established so far
- the constraints that matter
- the candidate options on the table (A vs B …)

Ground ONLY in the transcript; do not invent. Keep it short and decision-focused."""


def escalate_brief(agent, history):
    """Have the current agent distil the chat into a decision question + brief."""
    convo = "\n\n".join(
        f"{'User' if h['role'] == 'user' else agent.get('name', 'agent')}: {h['content']}"
        for h in history)
    spec = config.resolve_model(agent.get("model") or "claude_cli")
    return llm.call(spec, _ESCALATE_SYS, convo, max_tokens=800, temperature=0.2)


def escalate_to_discussion(agent, history, crew_name, mock=False):
    """Distil the chat → brief, then convene a crew on that decision question.

    The brief is injected as extra context and its leading '# …' line becomes the
    crew's task (overriding the crew default), so the panel debates THIS fork.
    Returns (brief, question, transcript). The crew run auto-saves to
    conversations/ + runs/ (sediment it to `decisions` afterwards).
    """
    from . import crew as _crew
    brief = escalate_brief(agent, history)
    question = next((ln.lstrip("# ").strip() for ln in brief.splitlines()
                     if ln.strip().startswith("#")),
                    "Review this technical-route decision")
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(config.CONV_DIR, exist_ok=True)
    brief_path = os.path.join(config.CONV_DIR,
                              f"escalate_{_slug(agent.get('name', 'agent'))}_{ts}.md")
    with open(brief_path, "w", encoding="utf-8") as fh:
        fh.write(f"# Escalation brief — from chat with {agent.get('name')}\n\n{brief}\n")
    transcript = _crew.run_crew(crew_name, extra_files=[brief_path],
                                task=question, mock=mock)
    return brief, question, transcript
