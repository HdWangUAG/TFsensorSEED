# MiniCrew skills

10 runnable skills, grouped by engine. Each group has its own folder with a `<group>_skill.md` doc + processing scripts. Skills are defined in `src/minicrew/core/skills_impl.py` (`@skill`); run them on the **🛠️ Skills** page or via the crew tool-request protocol.

_Regenerate: `minicrew skills --write`._

- **[`pyrosetta/`](pyrosetta/pyrosetta_skill.md)** — PyRosetta — flex-ddG energetics & mutation threading: `flexddg_score`, `retrodict`
- **[`pymol/`](pymol/pymol_skill.md)** — PyMOL — structural rendering & pocket analysis: `analyze_structure`, `pocket_mutation_view`
- **[`boltz/`](boltz/boltz_skill.md)** — Boltz-2 — co-folding pose & binding: `boltz_compare`
- **[`cheminformatics/`](cheminformatics/cheminformatics_skill.md)** — RDKit / ProLIF — ligand & interaction analysis: `ligand_descriptors`, `ligand_similarity`, `interaction_fingerprint`
- **[`ml/`](ml/ml_skill.md)** — ML — predictive models: `train_model`
- **[`literature/`](literature/literature_skill.md)** — Literature — web retrieval: `literature_search`
