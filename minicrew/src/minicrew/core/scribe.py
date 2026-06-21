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
