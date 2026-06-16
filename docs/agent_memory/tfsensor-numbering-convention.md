---
name: tfsensor-numbering-convention
description: TFsensorSEED canonical residue numbering = MODEL/design index everywhere; never experimental
metadata:
  type: feedback
---

User directive (2026-06-15): in TFsensorSEED use the **MODEL/design residue index** (the `data/AcrR_dimer.fasta` / PDB index we design on, 1..182) **everywhere** — code, figures, results, docs. **Do NOT use experimental construct numbering.** The experiment is +9 vs model, so the wet-lab labels map: **F128W = model F119W**, **L156R = model L147R**, and Arg123/E106 are already model index.

**Why:** dual numbering (model vs experimental) was causing confusion/chaos. **How to apply:** mutation identifiers are R123E, R123D, F119W, L147R; variant/result-dir prefixes are wt/f119w/l147r/r123e/r123d. The only place the wet-lab labels (F128W/L156R) appear is one `wetlab_alias` field in `data/mutants.json` for traceability. Past result directories were renamed l156r→l147r, f128w→f119w (path names; Boltz-internal manifests keep old strings but are inert). See [[tfsensor-stage3-pipeline]].
