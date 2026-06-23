# ml skills

ML — predictive models

_Auto-generated (`minicrew skills --write`). Skills are defined in `src/minicrew/core/skills_impl.py`; standalone processing scripts live in this folder._

### `train_model`
Train an XGBoost model on a CSV and report cross-validated performance + top feature importances. Give smiles_column to use RDKit descriptors as features; else numeric columns. Auto-detects classification vs regression.
- **args:**
  - `csv_path` (string, required) — CSV path (repo-relative ok)
  - `target_column` (string, required)
  - `smiles_column` (string, optional) — optional; SMILES column to featurise with RDKit
