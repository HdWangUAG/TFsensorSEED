# boltz skills

Boltz-2 — co-folding pose & binding

_Auto-generated (`minicrew skills --write`). Skills are defined in `src/minicrew/core/skills_impl.py`; standalone processing scripts live in this folder._

### `boltz_compare`
Fold WT vs mutant holo complex with Boltz-2 and compare POCKET + BINDING: returns each one's affinity_probability_binary (binding head), the holo DBD spacing (Å), and a rendered mutant pocket. LONG-RUNNING (GPU, ~5-15 min for two folds). Caveat: DL poses flip the steroid A-ring (~1/15 SAR-consistent) and single-structure opening doesn't predict amplitude — treat as COARSE structural evidence, not a binding/activation verdict (COMPUTATIONAL_BOUNDARY.md).
- **requires:** network · ⏳ long-running (≤2400s)
- **args:**
  - `mutations` (array, required) — model-numbering mutations, e.g. ['I61L','L85I']
  - `ligand` (string, optional) — steroid in data/steroid_panel.csv (default testosterone)
  - `seed` (number, optional) — Boltz seed (default 1)
