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

## Speeding up distillation — `minicrew distill`
Let the librarian draft the note and a second model fact-check the numbers:

```bash
pdftotext paper.pdf paper.txt                 # PDFs → text first
scripts/minicrew distill paper.txt --verify \
    --out minicrew/knowledge/literature/2022_lin_qacr.md
```

The draft anchors every number to its verbatim source sentence 〔src: "..."〕;
`--verify` runs a *different* model to cross-check each number against the text.
You still confirm the numbers + DOI + tags before it's trusted. Defaults:
librarian = `claude_cli`, checker = `openai` (override with `--model` /
`--check-model`).
