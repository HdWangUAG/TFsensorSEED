# `knowledge/` — typed project knowledge (the system's grounding)

Each subfolder is a knowledge **category** with a different **trust tier** (set in
`core/config.py:KNOWLEDGE_TRUST`). A crew opts in with a `knowledge:` list in its
YAML; every selected file is injected into the discussion, labelled with its
source path (provenance) and trust tier, so agents weigh evidence correctly.

| folder | what goes here | trust tier |
|---|---|---|
| `experimental/` | wet-lab methods + results (assays, readouts) | HIGH — ground truth |
| `literature/`   | distilled paper notes (claims + citation) | HIGH — check domain |
| `computational/`| tool capabilities, method params, resolution limits | MEDIUM — a lead |
| `pitfalls/`     | dev gotchas / lessons (避坑点) | HARD CONSTRAINT |

**To add knowledge:** drop a `.md` file in the right folder. Keep one
fact/finding per file, distilled (not raw PDFs/logs) — agents reason on claims,
and context is finite. Use the `_TEMPLATE.md` in each folder. `README.md` and
`_TEMPLATE.md` files are NOT injected.

`pitfalls/` also automatically pulls the repo's curated `docs/agent_memory/`, so
hard-won lessons ground every discussion without copying.
