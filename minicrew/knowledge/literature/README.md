# `literature/` — distilled paper notes

**Do not dump PDFs here.** Agents reason on *claims*, context is finite, and we
need per-claim provenance + trust. Distil each paper into one short note using
`_TEMPLATE.md` (one paper per file, named e.g. `2021_smith_acrr_pocket.md`).

## Suggested collection workflow

1. **Triage by relevance** as you add: `high` (directly about AcrR/TetR-family
   steroid recognition, allostery, the specific ligands), `method` (a tool /
   scoring technique you use), `background`. High-relevance first.
2. **Distil to claims + numbers**, not abstracts. The useful unit is "X mutation
   shifted specificity Y-fold under Z conditions", with the citation.
3. **Tag** by topic (`tags:` in frontmatter) so Phase-2 retrieval can pull only
   the relevant subset instead of every paper.
4. **Record applicability caveats** — a result in ERα or a different scaffold may
   not transfer to AcrR; say so, so an agent doesn't over-trust it.
5. **Keep the DOI/URL** — provenance is what makes a claim weigh more than a
   model's guess.

## Speeding up distillation (optional)
You can let an LLM draft the note from a paper, then you verify the numbers:
`claude -p "Distil this paper into the _TEMPLATE.md format" < paper.txt`.
Later this becomes a `literature_librarian` tool agent (fetch + parse + draft),
but a human check on the numbers stays in the loop.
