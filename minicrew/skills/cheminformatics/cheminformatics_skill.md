# cheminformatics skills

RDKit / ProLIF — ligand & interaction analysis

_Auto-generated (`minicrew skills --write`). Skills are defined in `src/minicrew/core/skills_impl.py`; standalone processing scripts live in this folder._

### `ligand_descriptors`
Compute physicochemical descriptors (MW, logP, H-bond donors/acceptors, TPSA, rings, aromatic rings, rotatable bonds) for a ligand given a name or SMILES.
- **args:**
  - `ligand` (string, required) — ligand name (e.g. estradiol) or SMILES

### `ligand_similarity`
Tanimoto (Morgan r2) similarity between two ligands (names or SMILES).
- **args:**
  - `ligand_a` (string, required)
  - `ligand_b` (string, required)

### `interaction_fingerprint`
ProLIF protein–ligand interaction fingerprint from a complex PDB: which protein residues contact the ligand and how (hydrophobic, H-bond, pi-stacking, …).
- **args:**
  - `pdb_path` (string, required) — path to a protein–ligand complex PDB (repo-relative ok)
  - `ligand_resname` (string, optional) — ligand residue name (default STR)
