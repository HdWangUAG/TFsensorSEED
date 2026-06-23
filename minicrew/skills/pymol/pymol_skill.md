# pymol skills

PyMOL — structural rendering & pocket analysis

_Auto-generated (`minicrew skills --write`). Skills are defined in `src/minicrew/core/skills_impl.py`; standalone processing scripts live in this folder._

**Processing scripts in this folder:** `pymol_analyze.py`

### `analyze_structure`
Run real PyMOL on a protein–ligand complex (PDB/CIF, incl. Boltz/Protenix predictions): returns the ligand, pocket residues within a cutoff, and polar (H-bond-like) ligand–protein contacts with distances, plus a rendered pocket image. Use to inspect a predicted pose (which residues line the pocket, is the 3-keto/OH H-bonded, is the orientation sane).
- **requires:** conda env `pyrosetta` · binaries `pymol`
- **args:**
  - `pdb_path` (string, required) — path to a complex PDB/CIF (repo-relative ok)
  - `ligand_resname` (string, optional) — ligand residue name; omit to auto-detect
  - `pocket_cutoff` (number, optional) — pocket radius in Å (default 5.0)

### `pocket_mutation_view`
Show a mutation's effect on the pocket: threads the mutation(s) onto a holo complex (PyMOL mutagenesis rotamer swap) and renders the WT vs mutant pocket SIDE-BY-SIDE in the same view, mutated residues highlighted. Use to visualise steric/chemical changes (e.g. a D-ring clash). NOT energy-minimised.
- **requires:** conda env `pyrosetta` · binaries `pymol` · ⏳ long-running (≤600s)
- **args:**
  - `pdb_path` (string, required) — holo complex PDB/CIF (repo-relative ok)
  - `mutations` (array, required) — mutations to thread, e.g. ['I61L','L85I']
  - `ligand_resname` (string, optional) — ligand residue name; omit to auto-detect
