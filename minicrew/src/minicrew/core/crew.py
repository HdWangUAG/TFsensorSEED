"""Crew loading + the discussion engine.

Two topologies, chosen per-crew via the `topology:` field:

  * parallel_blind  — every reviewer critiques the material INDEPENDENTLY (blind
                      to the others), then a moderator synthesises. Opinions are
                      genuinely uncorrelated; the moderator surfaces agreement /
                      disagreement instead of manufacturing consensus.
  * round_robin     — reviewers speak in turn over N rounds, each SEEING the
                      discussion so far, then the synthesiser closes. A real
                      debate that can converge (or pile on).

The information boundary — who sees what — is the whole design. It lives in
`_reviewer_prompt` (blind) vs `_round_prompt` (sees peers) vs `_moderator_prompt`
(sees every review). Change those three and you change the system's character.

For every turn we record `prompt_seen` — exactly what the agent received — so a
transcript explains not just what was said but why. That's the learning
instrument (see logger.py).
"""
from __future__ import annotations

import os
import sys

import yaml

from . import config, context, knowledge, llm, toolrun

# ----------------------------------------------------------------------------
# terminal styling (no-op when not a tty)
# ----------------------------------------------------------------------------
_TTY = sys.stdout.isatty()
_COLORS = ["\033[36m", "\033[32m", "\033[35m", "\033[33m", "\033[34m", "\033[31m"]
_BOLD, _DIM, _RESET = "\033[1m", "\033[2m", "\033[0m"
_WHITE = "\033[97m"


def _c(text, code):
    return f"{code}{text}{_RESET}" if _TTY else text


PROMPTS_DIR = config.PROMPTS_DIR


# ----------------------------------------------------------------------------
# loading
# ----------------------------------------------------------------------------
def crew_path(name):
    """Find a crew YAML by name across the configured crew dirs."""
    fname = name if name.endswith((".yaml", ".yml")) else name + ".yaml"
    for d in config.CREW_DIRS:
        p = os.path.join(d, fname)
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(
        f"crew {name!r} not found in: {', '.join(config.CREW_DIRS)}")


def load_crew(name):
    with open(crew_path(name), encoding="utf-8") as fh:
        crew = yaml.safe_load(fh)
    crew.setdefault("name", name)
    crew.setdefault("topology", "round_robin")
    crew.setdefault("rounds", 1)
    crew.setdefault("roles", [])
    if crew["topology"] not in ("round_robin", "parallel_blind"):
        raise ValueError(f"crew {name!r}: unknown topology {crew['topology']!r} "
                         "(use round_robin | parallel_blind)")
    if not crew["roles"]:
        raise ValueError(f"crew {name!r} defines no roles")
    return crew


def list_crews():
    found = {}
    for d in config.CREW_DIRS:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith((".yaml", ".yml")):
                found.setdefault(f.rsplit(".", 1)[0], os.path.join(d, f))
    return found


def _persona(role):
    """Inline `persona:` or the contents of `persona_file:` (under prompts/)."""
    if role.get("persona_file"):
        p = role["persona_file"]
        if not os.path.isabs(p):
            cand = os.path.join(PROMPTS_DIR, p)
            p = cand if os.path.isfile(cand) else os.path.join(config.REPO_ROOT, p)
        with open(p, encoding="utf-8") as fh:
            from .agents import split_frontmatter   # strip metadata, keep body
            return split_frontmatter(fh.read())[1].strip()
    return role.get("persona", "You are a helpful, critical expert.")


# ----------------------------------------------------------------------------
# prompt assembly  (the information boundary)
# ----------------------------------------------------------------------------
def _material(crew, ctx, evidence, role=None):
    parts = [f"## Material to review\n{ctx}"]
    if evidence and evidence != "(no context files provided)":
        parts.append("## Grounding evidence (treat as more reliable than your "
                     f"priors)\n{evidence}")
    task = crew.get("task", crew.get("description", ""))
    if crew.get("context_pack") and role is not None:
        # role-specific, budgeted, status-filtered retrieval over typed memory
        from . import context_pack
        pack, _stats = context_pack.build_pack(task, role.get("name"))
        parts.append(pack)
    else:
        kn = crew.get("_knowledge")
        if kn:
            parts.append("## Project knowledge — weigh each block by its stated "
                         f"TRUST tier\n{kn}")
    if crew.get("tools"):
        tb = toolrun.tools_block(crew["tools"])
        if tb:
            parts.append(tb)
    parts.append(f"## Task\n{task}")
    return parts


def _discussion_so_far(crew, transcript):
    """Render prior turns. With context_pack on, compress all-but-the-last few
    turns into a digest that PRESERVES who-said-what (so dissent survives) rather
    than repeating every turn verbatim as the discussion grows."""
    live = [t for t in transcript if t["ok"]]
    if not live:
        return "(you speak first)"
    keep = 4
    if crew.get("context_pack") and len(live) > keep:
        early, recent = live[:-keep], live[-keep:]
        digest = "\n".join(
            f"- **{t['role']}**: {' '.join(t['content'].split())[:200]}…" for t in early)
        recent_txt = "\n\n".join(f"**{t['role']}** ({t['alias']}):\n{t['content']}"
                                 for t in recent)
        return (f"_Earlier turns (compressed — each speaker's stance kept):_\n{digest}"
                f"\n\n_Most recent turns (verbatim):_\n{recent_txt}")
    return "\n\n".join(f"**{t['role']}** ({t['alias']}):\n{t['content']}" for t in live)


def _reviewer_prompt(crew, ctx, evidence, role):
    """Blind reviewer: input + evidence + task. NOT the other reviewers."""
    parts = _material(crew, ctx, evidence, role)
    cap = role.get("word_limit", 250)
    parts.append(f"## Your turn — {role['name']}\nCritique as this expert. Be "
                 f"concrete, cite specifics, order by severity. Keep it under "
                 f"~{cap} words. End with one clearly-labelled recommendation.")
    return "\n\n".join(parts)


def _round_prompt(crew, ctx, evidence, transcript, role):
    """Round-robin turn: input + evidence + discussion so far + task."""
    parts = _material(crew, ctx, evidence, role)
    parts.append(f"## Discussion so far\n{_discussion_so_far(crew, transcript)}")
    cap = role.get("word_limit", 250)
    parts.append(f"## Your turn — {role['name']}\nBuild on or push back against "
                 f"the others (don't just agree). Be concrete. Keep it under "
                 f"~{cap} words. End with one labelled recommendation.")
    return "\n\n".join(parts)


def _moderator_prompt(crew, ctx, evidence, transcript, synth):
    parts = [f"## Original material\n{ctx}"]
    if evidence and evidence != "(no context files provided)":
        parts.append(f"## Grounding evidence\n{evidence}")
    if crew.get("context_pack"):
        from . import context_pack
        pack, _stats = context_pack.build_pack(
            crew.get("task", crew.get("description", "")), synth.get("name", "Moderator"))
        parts.append(pack)
    else:
        kn = crew.get("_knowledge")
        if kn:
            parts.append(f"## Project knowledge — weigh by TRUST tier\n{kn}")
    for t in transcript:
        if t["ok"]:
            parts.append(f"## Review by {t['role']} ({t['alias']})\n{t['content']}")
    parts.append("## Your task\n" + synth.get("task",
        "Synthesise. Produce: (1) where reviewers AGREE, (2) where they DISAGREE "
        "(and which side is stronger), (3) the claim you can LEAST verify (flag "
        "for the human), (4) a prioritised, numbered must-fix list with an "
        "owner-role and concrete next step. Don't let agreement become false "
        "confidence."))
    return "\n\n".join(parts)


# ----------------------------------------------------------------------------
# invocation (real or mock)
# ----------------------------------------------------------------------------
def _mock_reply(role_name, alias, prompt):
    return (f"[MOCK {alias}] As {role_name} I reviewed the material "
            f"({len(prompt)} chars). My single biggest concern would go here, "
            f"followed by one concrete recommendation.")


def _invoke(role, prompt, mock):
    """Return (ok, alias, model, text). Never raises — failures become text."""
    spec = config.resolve_model(role["model"])
    if mock:
        return True, spec["alias"], spec["model"], _mock_reply(
            role["name"], spec["alias"], prompt)
    try:
        text = llm.call(spec, _persona(role), prompt,
                        max_tokens=role.get("max_tokens"),
                        temperature=role.get("temperature"))
        return True, spec["alias"], spec["model"], text
    except llm.LLMError as exc:
        return False, spec["alias"], spec["model"], f"[skipped — {exc}]"


def _maybe_run_tools(crew, role, text, transcript, on_event, rnd):
    """If the crew has tools enabled and the role's reply contains tool requests,
    execute them (allow-list enforced) and append a compact Tool-Runner turn so
    later agents see real computational results. Returns the appended record or None."""
    crew_tools = crew.get("tools")
    if not crew_tools:
        return None
    reqs = toolrun.parse_requests(text)
    if not reqs:
        return None
    allowed = role.get("tools") or crew_tools     # role may narrow the crew allow-list
    allowed = [t for t in allowed if t in crew_tools]
    results = toolrun.execute(reqs, allowed, requested_by=role["name"], on_event=on_event)
    body = "\n\n".join(r["compact"] for r in results)
    runner = {"name": "Tool-Runner"}
    rec = _record(runner, "skills", "—", "tool",
                  f"(deterministic skill execution requested by {role['name']})",
                  body, True)
    _print_turn(0, runner, "skills", "—", body, True, marker="▶")
    transcript.append(rec)
    _emit(on_event, type="turn", round=rnd, **rec)
    return rec


def _print_turn(idx, role, alias, model, text, ok, marker="●"):
    color = (_COLORS[idx % len(_COLORS)] if marker == "●" else _WHITE)
    print(_c(f"\n{marker} {role['name']}  [{alias}:{model}]", color + _BOLD))
    print(_c("  " + text, _DIM) if not ok else _indent(text))


def _indent(text):
    return "\n".join("  " + ln for ln in text.splitlines())


# ----------------------------------------------------------------------------
# the run loop
# ----------------------------------------------------------------------------
def _auto_sediment(crew, run_id, on_event):
    """Curate this run into typed memory right after it saves (the Memory-Curator
    automation): extract claim/decision/pitfall records + a decisions note, so
    memory accrues without a manual `minicrew sediment`."""
    import json
    from . import scribe
    try:
        rj = json.load(open(os.path.join(config.RUNS_DIR, run_id + ".json"),
                            encoding="utf-8"))
        spath, _ = scribe.sediment_record(rj, model=crew.get("scribe_model", "claude_cli"))
        print(_c(f"[curated] → {os.path.relpath(spath, config.REPO_ROOT)} "
                 f"(+ typed records)", _DIM))
        _emit(on_event, type="curated", run_id=run_id, path=spath)
    except Exception as exc:                       # never let curation break a run
        print(_c(f"[curate skipped — {exc}]", _DIM))


def run_crew(name, extra_files=None, rounds=None, topology=None,
             dry_run=False, mock=False, out_path=None, on_event=None, task=None,
             sediment=False):
    crew = load_crew(name)
    if task:                       # override the crew's default task (e.g. escalation)
        crew["task"] = task
    topology = topology or crew["topology"]
    rounds = rounds or crew.get("rounds", 1)
    ctx = context.build(crew.get("context_files"), extra_files)
    evidence = context.build(crew.get("evidence_files")) if crew.get("evidence_files") else ""
    # Real runs retrieve literature semantically (top-k vs the task); mock/dry-run
    # stay offline → fall back to whole-file injection.
    kn_query = None if (mock or dry_run) else (crew.get("task") or crew.get("description"))
    crew["_knowledge"] = knowledge.build(crew.get("knowledge"), query=kn_query)

    # Provider-aware tool routing guard: a role may only use NATIVE tool-calling
    # if its provider supports it; claude_cli etc. use the Tool-Request protocol.
    for role in crew["roles"]:
        toolrun.assert_tool_routing(role, config.resolve_model(role["model"]))

    tag = "  [DRY RUN]" if dry_run else ("  [MOCK]" if mock else "")
    print(_c(f"\n=== MiniCrewAI: {crew['name']} ===", _BOLD))
    print(_c(crew.get("task", crew.get("description", "")).strip(), _DIM))
    kn_cats = ", ".join(crew.get("knowledge") or []) or "none"
    print(_c(f"topology={topology}  roles={len(crew['roles'])}  knowledge={kn_cats}"
             + (f"  rounds={rounds}" if topology == "round_robin" else "") + tag,
             _DIM))

    if dry_run:
        return _dry_run(crew, ctx, evidence, topology, rounds)

    _emit(on_event, type="start", crew=crew["name"], topology=topology,
          task=crew.get("task", ""), roles=[r["name"] for r in crew["roles"]],
          rounds=rounds)

    transcript = []
    if topology == "parallel_blind":
        for i, role in enumerate(crew["roles"]):
            prompt = _reviewer_prompt(crew, ctx, evidence, role)
            ok, alias, model, text = _invoke(role, prompt, mock)
            _print_turn(i, role, alias, model, text, ok)
            rec = _record(role, alias, model, "reviewer", prompt, text, ok)
            transcript.append(rec)
            _emit(on_event, type="turn", round=1, **rec)
            if ok:
                _maybe_run_tools(crew, role, text, transcript, on_event, 1)
    else:  # round_robin
        for rnd in range(1, rounds + 1):
            if rounds > 1:
                print(_c(f"\n----- round {rnd}/{rounds} -----", _BOLD))
            for i, role in enumerate(crew["roles"]):
                prompt = _round_prompt(crew, ctx, evidence, transcript, role)
                ok, alias, model, text = _invoke(role, prompt, mock)
                _print_turn(i, role, alias, model, text, ok)
                rec = _record(role, alias, model, "reviewer", prompt, text, ok)
                transcript.append(rec)
                _emit(on_event, type="turn", round=rnd, **rec)
                if ok:
                    _maybe_run_tools(crew, role, text, transcript, on_event, rnd)

    synth = crew.get("synthesizer")
    if synth:
        prompt = _moderator_prompt(crew, ctx, evidence, transcript, synth)
        sr = dict(synth)
        sr.setdefault("name", "Moderator")
        sr.setdefault("temperature", 0.3)
        sr.setdefault("max_tokens", 1500)
        ok, alias, model, text = _invoke(sr, prompt, mock)
        _print_turn(0, sr, alias, model, text, ok, marker="■")
        rec = _record(sr, alias, model, "moderator", prompt, text, ok)
        transcript.append(rec)
        _emit(on_event, type="turn", round=0, **rec)

    from . import logger
    rec = logger.save_run(crew, topology, transcript, out_path)
    print(_c(f"\n[saved] conversations/{rec['run_id']}.md  +  runs/{rec['run_id']}.json", _DIM))
    _emit(on_event, type="done", run_id=rec["run_id"])
    if (sediment or crew.get("auto_sediment")) and not mock:
        _auto_sediment(crew, rec["run_id"], on_event)
    return transcript


def _emit(on_event, **event):
    if on_event:
        try:
            on_event(event)
        except Exception:        # a UI callback must never break the run
            pass


def _record(role, alias, model, kind, prompt, text, ok):
    return {"role": role["name"], "alias": alias, "model": model, "kind": kind,
            "prompt_seen": prompt, "content": text, "ok": ok}


def _dry_run(crew, ctx, evidence, topology, rounds):
    """Assemble and print prompts without any API call."""
    transcript = []
    roles = crew["roles"]
    for i, role in enumerate(roles):
        if topology == "parallel_blind":
            prompt = _reviewer_prompt(crew, ctx, evidence, role)
        else:
            prompt = _round_prompt(crew, ctx, evidence, transcript, role)
            transcript.append(_record(role, role["model"], "?", "reviewer",
                                      prompt, "(dry-run placeholder)", True))
        spec = config.resolve_model(role["model"])
        print(_c(f"\n● {role['name']}  [{spec['alias']}:{spec['model']}]", _BOLD))
        print(_indent(prompt)[:1400] + " …")
    return transcript
