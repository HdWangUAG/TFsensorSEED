# pyrosetta skills

PyRosetta — flex-ddG energetics & mutation threading

_Auto-generated (`minicrew skills --write`). Skills are defined in `src/minicrew/core/skills_impl.py`; standalone processing scripts live in this folder._

**Processing scripts in this folder:** `thread_mutant.py`

### `flexddg_score`
Estimate the interface binding energy of a (multi-)mutant for one steroid via flex-ddG (PyRosetta): threads the mutation(s) onto a holo pose, flex-relaxes, and reports dG_separated and ΔΔG vs WT. NOTE: binding-ΔΔG is a COARSE ranker — see the computational-boundary note; do not gate selectivity on a ~1 kcal/mol margin.
- **requires:** conda env `pyrosetta` · ⏳ long-running (≤1800s)
- **args:**
  - `pdb_path` (string, required) — holo complex pose (PDB/CIF, repo-relative ok)
  - `mutations` (array, required) — model-numbering mutations, e.g. ['I61L','L85I']
  - `ligand` (string, optional) — steroid name in data/steroid_panel.csv (default testosterone)
  - `seed` (string, optional) — PyRosetta seed (default '1')

### `retrodict`
Run the orientation-corrected flex-ddG retrodiction benchmark (tfsensor.ml.bo.retrodict): scores WT + known singles on SAR-consistent poses and checks WT steroid order + per-single selectivity shift vs the empirical scan. LONG-RUNNING (many flex-ddG workers). Returns the verdict.
- **requires:** conda env `pyrosetta` · ⏳ long-running (≤5400s)
- **args:**
  - `jobs` (number, optional) — parallel workers (default 6)
