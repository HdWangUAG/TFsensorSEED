"""Adversarial verification — check a discussion's claims against the evidence.

Guards the closed loop: before consensus/decisions sediment into knowledge, a
verifier (ideally a DIFFERENT model than the discussants/scribe) checks each
claim against the project's *external* evidence (literature / experimental /
pitfalls / prior decisions) — not the transcript it came from — and flags
unsupported or contradicted ones, so only solid knowledge accrues.
"""
from __future__ import annotations

import re

from . import config, knowledge, llm

_VERIFY_SYS = """\
You are a strict scientific fact-checker. For EACH numbered claim, judge it ONLY
against the GROUNDING evidence (not your own priors):
  SUPPORTED    — the grounding backs it
  UNSUPPORTED  — not found in the grounding (may still be true; just unverified)
  CONTRADICTED — the grounding conflicts with it
Output exactly one line per claim:
  <n>. <SUPPORTED|UNSUPPORTED|CONTRADICTED> — <short reason, cite the grounding>
Default to UNSUPPORTED when unsure."""

_GROUNDING_CATS = ["literature", "experimental", "pitfalls", "decisions"]


def claims_from_note(note_md):
    """Pull the bullet claims under Consensus + Decisions from a scribe note."""
    claims, section = [], None
    for line in note_md.splitlines():
        h = line.strip().lower()
        if h.startswith("## "):
            section = "keep" if ("consensus" in h or "decision" in h) else None
        elif section and line.strip().startswith("- ") and "(none)" not in line.lower():
            claims.append(line.strip()[2:].strip())
    return claims


def claims_from_text(text, limit=20):
    """Pull bullet / numbered claim lines from any text (e.g. a synthesis)."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(("- ", "* ")) or re.match(r"^\d+[.)]\s", s):
            c = re.sub(r"^[-*\d.)\s]+", "", s).strip().lstrip("*").strip()
            if len(c) > 15:
                out.append(c)
    return out[:limit]


def verify_claims(claims, model="openai", grounding=None):
    """Return (verdict_text, counts) for a list of claims vs project evidence."""
    if not claims:
        return "(no claims to verify)", {"SUPPORTED": 0, "UNSUPPORTED": 0,
                                         "CONTRADICTED": 0}
    if grounding is None:
        grounding = knowledge.build(_GROUNDING_CATS) or "(no project evidence on file)"
    spec = config.resolve_model(model)
    numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(claims))
    prompt = f"GROUNDING (project evidence):\n{grounding}\n\n---\nCLAIMS:\n{numbered}"
    text = llm.call(spec, _VERIFY_SYS, prompt, max_tokens=1500, temperature=0)
    counts = {v: len(re.findall(rf"\b{v}\b", text)) for v in
              ("SUPPORTED", "UNSUPPORTED", "CONTRADICTED")}
    return text, counts
