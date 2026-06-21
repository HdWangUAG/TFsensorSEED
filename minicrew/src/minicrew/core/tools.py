"""Tool registry — real functions agents can call (Phase 3 tool-calling).

Each tool is a Python function with a name, description and JSON-schema params.
The first batch is RDKit cheminformatics (real numbers for the ligand side of the
project). Add PyRosetta / ESM2 / XGBoost tools here the same way later.
"""
from __future__ import annotations

# A few project-relevant ligands so agents can pass a name instead of SMILES.
KNOWN_SMILES = {
    "estradiol": "C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc43)[C@@H]1CC[C@@H]2O",
    "testosterone": "C[C@]12CC[C@H]3[C@@H](CCC4=CC(=O)CC[C@]34C)[C@@H]1CC[C@@H]2O",
    "progesterone": "CC(=O)[C@H]1CC[C@H]2[C@@H]3CCC4=CC(=O)CC[C@]4(C)[C@H]3CC[C@]12C",
    "cortisol": "C[C@]12C[C@H](O)[C@H]3[C@@H](CCC4=CC(=O)CC[C@]34C)[C@@H]1CC[C@@]2(O)C(=O)CO",
}


def _mol(smiles_or_name):
    from rdkit import Chem
    s = KNOWN_SMILES.get(str(smiles_or_name).strip().lower(), smiles_or_name)
    return Chem.MolFromSmiles(s), s


def ligand_descriptors(ligand):
    """Physicochemical descriptors for a ligand (name or SMILES)."""
    from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors
    mol, smi = _mol(ligand)
    if mol is None:
        return {"error": f"could not parse {ligand!r}"}
    return {
        "input": ligand, "smiles": smi,
        "MW": round(Descriptors.MolWt(mol), 2),
        "logP": round(Crippen.MolLogP(mol), 2),
        "HBD": rdMolDescriptors.CalcNumHBD(mol),
        "HBA": rdMolDescriptors.CalcNumHBA(mol),
        "TPSA": round(rdMolDescriptors.CalcTPSA(mol), 1),
        "rings": rdMolDescriptors.CalcNumRings(mol),
        "aromatic_rings": rdMolDescriptors.CalcNumAromaticRings(mol),
        "rot_bonds": rdMolDescriptors.CalcNumRotatableBonds(mol),
    }


def ligand_similarity(ligand_a, ligand_b):
    """Tanimoto similarity (Morgan r2) between two ligands (names or SMILES)."""
    from rdkit.Chem import AllChem, DataStructs
    ma, _ = _mol(ligand_a)
    mb, _ = _mol(ligand_b)
    if ma is None or mb is None:
        return {"error": "could not parse one of the ligands"}
    fa = AllChem.GetMorganFingerprintAsBitVect(ma, 2, 2048)
    fb = AllChem.GetMorganFingerprintAsBitVect(mb, 2, 2048)
    return {"ligand_a": ligand_a, "ligand_b": ligand_b,
            "tanimoto": round(DataStructs.TanimotoSimilarity(fa, fb), 3)}


def interaction_fingerprint(pdb_path, ligand_resname="STR"):
    """ProLIF protein–ligand interaction fingerprint from a complex PDB:
    which protein residues contact the ligand and via what interaction type."""
    import os
    if not os.path.isabs(pdb_path):
        from . import config
        pdb_path = os.path.join(config.REPO_ROOT, pdb_path)
    try:
        import MDAnalysis as mda
        import prolif as plf
        u = mda.Universe(pdb_path)
        lig_ag = u.select_atoms(f"resname {ligand_resname}")
        prot_ag = u.select_atoms("protein")
        if len(lig_ag) == 0:
            return {"error": f"no ligand with resname {ligand_resname!r} in {pdb_path}"}
        # NoImplicit=False: allow implicit H (these PDBs have no explicit H) — H-bond
        # calls are then approximate, but hydrophobic / pi / contacts are recovered.
        lig = plf.Molecule.from_mda(lig_ag, NoImplicit=False)
        prot = plf.Molecule.from_mda(prot_ag, NoImplicit=False)
        fp = plf.Fingerprint()
        fp.run_from_iterable([lig], prot, progress=False)
        df = fp.to_dataframe()
    except Exception as exc:
        return {"error": f"ProLIF failed: {exc}"}
    by_res = {}
    for col in df.columns:
        prot_res, inter = col[1], col[-1]
        by_res.setdefault(str(prot_res), set()).add(str(inter))
    summary = {r: sorted(v) for r, v in sorted(by_res.items())}
    return {"pdb": os.path.basename(pdb_path), "ligand_resname": ligand_resname,
            "n_interacting_residues": len(summary), "interactions": summary}


def train_model(csv_path, target_column, smiles_column=None):
    """Train an XGBoost model on a CSV and report cross-validated performance +
    top feature importances. If `smiles_column` is given, RDKit descriptors are
    the features; otherwise the numeric columns are. Auto-detects classification
    vs regression from the target."""
    import os
    import numpy as np
    import pandas as pd
    if not os.path.isabs(csv_path):
        from . import config
        csv_path = os.path.join(config.REPO_ROOT, csv_path)
    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:
        return {"error": f"could not read {csv_path}: {exc}"}
    if target_column not in df.columns:
        return {"error": f"target {target_column!r} not in columns {list(df.columns)}"}

    if smiles_column and smiles_column in df.columns:
        rows = [ligand_descriptors(s) for s in df[smiles_column]]
        feat = pd.DataFrame([{k: v for k, v in r.items()
                              if isinstance(v, (int, float))} for r in rows])
        feat_names = list(feat.columns)
        X = feat.values
    else:
        num = df.select_dtypes("number").drop(columns=[target_column], errors="ignore")
        feat_names, X = list(num.columns), num.values
    y_raw = df[target_column]
    n = len(df)
    classification = (y_raw.dtype == object) or (y_raw.nunique() <= 10
                                                 and y_raw.dtype != float)
    try:
        import xgboost as xgb
        from sklearn.metrics import accuracy_score, r2_score
        from sklearn.model_selection import cross_val_predict
        if classification:
            classes, y = np.unique(y_raw, return_inverse=True)
            model = xgb.XGBClassifier(n_estimators=200, max_depth=3,
                                      verbosity=0, use_label_encoder=False)
            metric = "accuracy"
        else:
            y = y_raw.values.astype(float)
            model = xgb.XGBRegressor(n_estimators=200, max_depth=3, verbosity=0)
            metric = "R2"
        cv = min(5, n)
        score, note = None, ""
        if n >= 6 and cv >= 2:
            pred = cross_val_predict(model, X, y, cv=cv)
            score = (accuracy_score(y, pred) if classification
                     else r2_score(y, pred))
        else:
            note = f"only {n} rows — too few for CV; importances from a full fit"
        model.fit(X, y)
        imp = sorted(zip(feat_names, model.feature_importances_),
                     key=lambda t: -t[1])[:8]
        out = {"rows": n, "task": "classification" if classification else "regression",
               "features": feat_names,
               "top_importances": [{"feature": f, "importance": round(float(i), 3)}
                                   for f, i in imp]}
        if score is not None:
            out[f"cv_{metric}"] = round(float(score), 3)
        if note:
            out["note"] = note
        return out
    except Exception as exc:
        return {"error": f"training failed: {exc}"}


REGISTRY = {
    "ligand_descriptors": {
        "fn": ligand_descriptors,
        "description": "Compute physicochemical descriptors (MW, logP, H-bond "
                       "donors/acceptors, TPSA, rings, aromatic rings, rotatable "
                       "bonds) for a ligand given a name or SMILES.",
        "parameters": {
            "type": "object",
            "properties": {"ligand": {"type": "string",
                           "description": "ligand name (e.g. estradiol) or SMILES"}},
            "required": ["ligand"]},
    },
    "ligand_similarity": {
        "fn": ligand_similarity,
        "description": "Tanimoto (Morgan) similarity between two ligands "
                       "(names or SMILES).",
        "parameters": {
            "type": "object",
            "properties": {
                "ligand_a": {"type": "string"},
                "ligand_b": {"type": "string"}},
            "required": ["ligand_a", "ligand_b"]},
    },
    "interaction_fingerprint": {
        "fn": interaction_fingerprint,
        "description": "ProLIF protein–ligand interaction fingerprint from a "
                       "complex PDB: which protein residues contact the ligand "
                       "and how (hydrophobic, H-bond, pi-stacking, …).",
        "parameters": {
            "type": "object",
            "properties": {
                "pdb_path": {"type": "string",
                             "description": "path to a protein–ligand complex PDB "
                                            "(repo-relative ok)"},
                "ligand_resname": {"type": "string",
                                   "description": "ligand residue name (default STR)"}},
            "required": ["pdb_path"]},
    },
    "train_model": {
        "fn": train_model,
        "description": "Train an XGBoost model on a CSV and report cross-validated "
                       "performance + top feature importances. Give smiles_column "
                       "to use RDKit descriptors as features.",
        "parameters": {
            "type": "object",
            "properties": {
                "csv_path": {"type": "string", "description": "CSV path (repo-relative ok)"},
                "target_column": {"type": "string"},
                "smiles_column": {"type": "string",
                                  "description": "optional; column of SMILES to "
                                                 "featurise with RDKit"}},
            "required": ["csv_path", "target_column"]},
    },
}


def openai_schemas(names=None):
    """Tool list in OpenAI function-calling format."""
    names = names or list(REGISTRY)
    return [{"type": "function", "function": {
                "name": n, "description": REGISTRY[n]["description"],
                "parameters": REGISTRY[n]["parameters"]}}
            for n in names if n in REGISTRY]
