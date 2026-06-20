"""1:1 conversation with a single agent, optionally grounded in project knowledge.

Stateless: the caller keeps the history and passes it in each turn. The agent's
persona is the system prompt; with `ground=True` the relevant pitfalls + top-k
literature for the message are injected (same trust-tiered knowledge the crews
use). Distinct from a crew: this is a brainstorm with one expert, not a panel.
"""
from __future__ import annotations

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
