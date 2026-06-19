"""Distil a paper's text into a literature knowledge note (semi-automated).

LLMs structure claims well but misread exact numbers — so the librarian anchors
every quantitative claim to its verbatim source sentence, and an optional checker
(a *different* model, for independence) verifies each number against the original
text and flags anything unsupported. The human confirms before it enters
knowledge/literature/.

This is an extraction pipeline (1–2 agents), not a discussion — hence its own
module + CLI subcommand rather than a crew.
"""
from __future__ import annotations

import os

from . import config, llm

_LIBRARIAN_SYS = """\
You are a meticulous scientific librarian distilling ONE paper into a structured
note for a protein-engineering project (an AcrR steroid biosensor). Rules:
- Fill the provided template EXACTLY: same frontmatter keys, same section
  headings. Output only the filled note (Markdown), nothing else.
- Extract ONLY what the text supports. Never invent numbers, DOIs, or claims.
- After EVERY quantitative claim, append the verbatim source sentence as
  〔src: "..."〕 so a human can verify in seconds.
- If a field is not determinable from the text, write TODO — do not guess.
- Claim-level and concise; capture effect sizes and conditions, not prose."""

_CHECKER_SYS = """\
You are a strict fact-checker. You are given a paper's text and a draft note
distilled from it. For EACH quantitative claim in the draft, verify it against
the text and report one line each:
  ✓ supported | ✗ NOT FOUND in text | ⚠ MISREAD (give the correct value)
quoting the supporting text. Also flag any DOI/author/year that can't be
confirmed. Default to ⚠ when unsure. End with exactly one line:
  VERDICT: clean | needs-fixes"""


def _template():
    p = os.path.join(config.KNOWLEDGE_DIR, "literature", "_TEMPLATE.md")
    try:
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return "(template missing)"


def distill(text, model="claude_cli", mock=False):
    """Return a filled literature note (Markdown) drafted from `text`."""
    if mock:
        return ("---\ntitle: <MOCK>\n---\n## Claim / finding\n"
                "- [MOCK distill] one claim 〔src: \"...\"〕")
    spec = config.resolve_model(model)
    prompt = (f"Template to fill:\n\n{_template()}\n\n"
              f"---\nPaper text:\n\n{text}")
    return llm.call(spec, _LIBRARIAN_SYS, prompt, max_tokens=2500, temperature=0.2)


def verify(text, draft, model="openai", mock=False):
    """Cross-check the draft's numbers against the source text."""
    if mock:
        return "✓ supported (mock)\nVERDICT: clean"
    spec = config.resolve_model(model)
    prompt = f"Paper text:\n\n{text}\n\n---\nDraft note:\n\n{draft}"
    return llm.call(spec, _CHECKER_SYS, prompt, max_tokens=2000, temperature=0)
