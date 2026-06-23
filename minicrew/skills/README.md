# MiniCrew skills

Runnable scientific capabilities. Each is defined in `src/minicrew/core/skills_impl.py` (registered via `@skill`); the standalone processing scripts they shell out to live in `skills/scripts/`. Use them on the **🛠️ Skills** page, or let crew agents request them via the tool-request protocol.

_Auto-generated from the registry — regenerate with `minicrew skills --write`._

**10 skills:** `analyze_structure`, `boltz_compare`, `flexddg_score`, `interaction_fingerprint`, `ligand_descriptors`, `ligand_similarity`, `literature_search`, `pocket_mutation_view`, `retrodict`, `train_model`

## `analyze_structure`
Run real PyMOL on a protein–ligand complex (PDB/CIF, incl. Boltz/Protenix predictions): returns the ligand, pocket residues within a cutoff, and polar (H-bond-like) ligand–protein contacts with distances, plus a rendered pocket image. Use to inspect a predicted pose (which residues line the pocket, is the 3-keto/OH H-bonded, is the orientation sane).
- **requires:** conda env `pyrosetta` · binaries `pymol`
- **args:**
  - `pdb_path` (string, required) — path to a complex PDB/CIF (repo-relative ok)
  - `ligand_resname` (string, optional) — ligand residue name; omit to auto-detect
  - `pocket_cutoff` (number, optional) — pocket radius in Å (default 5.0)

## `boltz_compare`
Fold WT vs mutant holo complex with Boltz-2 and compare POCKET + BINDING: returns each one's affinity_probability_binary (binding head), the holo DBD spacing (Å), and a rendered mutant pocket. LONG-RUNNING (GPU, ~5-15 min for two folds). Caveat: DL poses flip the steroid A-ring (~1/15 SAR-consistent) and single-structure opening doesn't predict amplitude — treat as COARSE structural evidence, not a binding/activation verdict (COMPUTATIONAL_BOUNDARY.md).
- **requires:** network · ⏳ long-running (≤2400s)
- **args:**
  - `mutations` (array, required) — model-numbering mutations, e.g. ['I61L','L85I']
  - `ligand` (string, optional) — steroid in data/steroid_panel.csv (default testosterone)
  - `seed` (number, optional) — Boltz seed (default 1)

## `flexddg_score`
Estimate the interface binding energy of a (multi-)mutant for one steroid via flex-ddG (PyRosetta): threads the mutation(s) onto a holo pose, flex-relaxes, and reports dG_separated and ΔΔG vs WT. NOTE: binding-ΔΔG is a COARSE ranker — see the computational-boundary note; do not gate selectivity on a ~1 kcal/mol margin.
- **requires:** conda env `pyrosetta` · ⏳ long-running (≤1800s)
- **args:**
  - `pdb_path` (string, required) — holo complex pose (PDB/CIF, repo-relative ok)
  - `mutations` (array, required) — model-numbering mutations, e.g. ['I61L','L85I']
  - `ligand` (string, optional) — steroid name in data/steroid_panel.csv (default testosterone)
  - `seed` (string, optional) — PyRosetta seed (default '1')

## `interaction_fingerprint`
ProLIF protein–ligand interaction fingerprint from a complex PDB: which protein residues contact the ligand and how (hydrophobic, H-bond, pi-stacking, …).
- **args:**
  - `pdb_path` (string, required) — path to a protein–ligand complex PDB (repo-relative ok)
  - `ligand_resname` (string, optional) — ligand residue name (default STR)

## `ligand_descriptors`
Compute physicochemical descriptors (MW, logP, H-bond donors/acceptors, TPSA, rings, aromatic rings, rotatable bonds) for a ligand given a name or SMILES.
- **args:**
  - `ligand` (string, required) — ligand name (e.g. estradiol) or SMILES

## `ligand_similarity`
Tanimoto (Morgan r2) similarity between two ligands (names or SMILES).
- **args:**
  - `ligand_a` (string, required)
  - `ligand_b` (string, required)

## `literature_search`
Search the web literature (Semantic Scholar or OpenAlex — open APIs, no key) for papers on a topic: returns title, authors, year, venue, DOI, citation count, abstract, and URL. Use to find external evidence / precedents; pair with `distill` to store a vetted note. Abstracts only (not full text); verify claims against the source before trusting.
- **requires:** network
- **args:**
  - `query` (string, required) — search query (keywords/phrase)
  - `limit` (number, optional) — max papers (default 8)
  - `source` (string, optional) — openalex (default) | semantic_scholar
  - `year_from` (number, optional) — optional earliest year

## `pocket_mutation_view`
Show a mutation's effect on the pocket: threads the mutation(s) onto a holo complex (PyMOL mutagenesis rotamer swap) and renders the WT vs mutant pocket SIDE-BY-SIDE in the same view, mutated residues highlighted. Use to visualise steric/chemical changes (e.g. a D-ring clash). NOT energy-minimised.
- **requires:** conda env `pyrosetta` · binaries `pymol` · ⏳ long-running (≤600s)
- **args:**
  - `pdb_path` (string, required) — holo complex PDB/CIF (repo-relative ok)
  - `mutations` (array, required) — mutations to thread, e.g. ['I61L','L85I']
  - `ligand_resname` (string, optional) — ligand residue name; omit to auto-detect

## `retrodict`
Run the orientation-corrected flex-ddG retrodiction benchmark (tfsensor.ml.bo.retrodict): scores WT + known singles on SAR-consistent poses and checks WT steroid order + per-single selectivity shift vs the empirical scan. LONG-RUNNING (many flex-ddG workers). Returns the verdict.
- **requires:** conda env `pyrosetta` · ⏳ long-running (≤5400s)
- **args:**
  - `jobs` (number, optional) — parallel workers (default 6)

## `train_model`
Train an XGBoost model on a CSV and report cross-validated performance + top feature importances. Give smiles_column to use RDKit descriptors as features; else numeric columns. Auto-detects classification vs regression.
- **args:**
  - `csv_path` (string, required) — CSV path (repo-relative ok)
  - `target_column` (string, required)
  - `smiles_column` (string, optional) — optional; SMILES column to featurise with RDKit
