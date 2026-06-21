"""Scribe — sediment a discussion into durable project knowledge.

Closes the loop: after a crew discusses, the scribe reads the transcript and
writes a structured note (consensus, decisions, open questions, candidate
pitfalls) into knowledge/decisions/ — grounded ONLY in the transcript. Future
discussions that include the `decisions` knowledge layer then build on it, so the
system accumulates project understanding instead of forgetting each run.

Safety: candidate pitfalls are recorded *inside* the decisions note (labelled),
NOT auto-promoted to the HARD-CONSTRAINT pitfalls layer — a human curates those.
"""
from __future__ import annotations

import datetime as _dt
import os

from . import config, llm

_SCRIBE_SYS = """\
You are the project scribe. From the discussion transcript, extract the DURABLE
knowledge worth carrying into future discussions — grounded ONLY in the
transcript; never invent. Output Markdown with exactly these sections:

## Consensus / findings
- <points the experts agreed on, with the specifics>

## Decisions
- <decision> — owner: <role> — next step: <concrete action>

## Open questions
- <what remains unresolved / needs a human or an experiment>

## Candidate pitfalls (for human review — not yet a hard rule)
- <a "do not repeat" lesson surfaced here, if any>

Be concise and concrete. If a section has nothing, write "- (none)"."""


def _transcript_text(record):
    return "\n\n".join(
        f"**{o.get('agent')}** ({o.get('alias')}):\n{o.get('reply', '')}"
        for o in record.get("outputs", []) if o.get("ok", True))


def sediment_run(record, model="claude_cli", verify_model=None):
    """Extract a decisions note from a run record; write it to knowledge/
    decisions/ and return (path, content). If `verify_model` is set, a (different)
    model fact-checks the consensus/decisions against project evidence first and
    the verdicts are appended — so the loop only accrues vetted knowledge."""
    from . import verify
    crew = record.get("crew", "discussion")
    run_id = record.get("run_id", "?")
    task = record.get("task", "")
    prompt = (f"Crew: {crew}\nTask: {task}\n\n"
              f"Transcript:\n\n{_transcript_text(record)}")
    spec = config.resolve_model(model)
    body = llm.call(spec, _SCRIBE_SYS, prompt, max_tokens=1500, temperature=0.2)

    verified = None
    verify_section = ""
    if verify_model:
        claims = verify.claims_from_note(body)
        vtext, counts = verify.verify_claims(claims, model=verify_model)
        verified = verify_model
        verify_section = (f"\n## Verification (by {verify_model} — "
                          f"{counts['SUPPORTED']}✓ / {counts['UNSUPPORTED']}⚠ / "
                          f"{counts['CONTRADICTED']}✗ vs project evidence)\n{vtext}\n")

    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(config.DECISIONS_DIR, exist_ok=True)
    fm = (f"---\ntitle: Decisions — {crew}\ntype: decisions\n"
          f"source_run: {run_id}\ncrew: {crew}\ndate: {ts}\ntrust: MEDIUM\n"
          + (f"verified_by: {verified}\n" if verified else "") + "---\n\n")
    note = (fm + f"_Sedimented from discussion run `{run_id}`._\n\n"
            f"{body.strip()}\n{verify_section}")
    path = os.path.join(config.DECISIONS_DIR, f"{ts}_{crew}_decisions.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(note)
    return path, note


_ENGINEERING_SYS = """\
You are the project engineering scribe. From a 1:1 chat transcript between the
user and a single expert agent (an EXECUTION/engineering session, not a strategy
debate), extract the durable TACTICAL know-how — grounded ONLY in the transcript;
never invent. Output Markdown with exactly these sections:

## What was built / done
- <concrete artifacts, code, commands, results>

## Key technical choices (and why)
- <choice> — because <reason / constraint>

## Gotchas / pitfalls hit
- <the trap + how it was resolved or worked around>

## Deviations from the plan
- <where execution diverged from the intended technical route, and why>

## TODO / follow-ups
- <unfinished threads, next concrete actions>

Be concise and concrete (file paths, flags, numbers). If a section has nothing,
write "- (none)"."""


def sediment_chat(record, model="claude_cli", verify_model=None):
    """Sediment a 1:1 CHAT record into an *engineering* note (knowledge/engineering/).

    Distinct from sediment_run: chat captures execution-level know-how / gotchas /
    route changes, so it gets an engineering schema and a separate, lower-stakes
    knowledge layer rather than the strategic `decisions` layer.
    """
    from . import verify
    agent = record.get("agent") or record.get("crew", "chat")
    run_id = record.get("run_id", "?")
    task = record.get("task", "")
    prompt = (f"Agent: {agent}\nTopic: {task}\n\n"
              f"Transcript:\n\n{_transcript_text(record)}")
    spec = config.resolve_model(model)
    body = llm.call(spec, _ENGINEERING_SYS, prompt, max_tokens=1500, temperature=0.2)

    verified = None
    verify_section = ""
    if verify_model:
        claims = verify.claims_from_note(body)
        vtext, counts = verify.verify_claims(claims, model=verify_model)
        verified = verify_model
        verify_section = (f"\n## Verification (by {verify_model} — "
                          f"{counts['SUPPORTED']}✓ / {counts['UNSUPPORTED']}⚠ / "
                          f"{counts['CONTRADICTED']}✗ vs project evidence)\n{vtext}\n")

    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = str(agent).lower().replace("/", "-").replace(" ", "_")
    os.makedirs(config.ENGINEERING_DIR, exist_ok=True)
    fm = (f"---\ntitle: Engineering — {agent}\ntype: engineering\n"
          f"source_run: {run_id}\nagent: {agent}\ndate: {ts}\ntrust: MEDIUM\n"
          + (f"verified_by: {verified}\n" if verified else "") + "---\n\n")
    note = (fm + f"_Sedimented from chat `{run_id}` with {agent}._\n\n"
            f"{body.strip()}\n{verify_section}")
    path = os.path.join(config.ENGINEERING_DIR, f"{ts}_{slug}_engineering.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(note)
    return path, note


def sediment_record(record, model="claude_cli", verify_model=None):
    """Dispatch by record kind: chat -> engineering note, else -> decisions note."""
    if record.get("kind") == "chat":
        return sediment_chat(record, model=model, verify_model=verify_model)
    return sediment_run(record, model=model, verify_model=verify_model)
