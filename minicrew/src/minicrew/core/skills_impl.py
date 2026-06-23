"""Skill implementations — the actual scientific capabilities, registered via @skill.

Each function returns the legacy plain dict (success payload, optionally with an
`image` key; or `{"error": ...}`); `skills.Skill.run` wraps it into a SkillResult
with provenance. Path-taking skills use `safe_input_path` (repo-confined). Heavy
compute (PyMOL / flex-ddG / retrodict) runs as a subprocess in the `pyrosetta`
conda env — never in `minicrew/.venv`.
"""
from __future__ import annotations

import json
import os

from . import config
from .skills import (skill, safe_input_path, run_subprocess, conda_python, run_id)

# --- project-relevant ligands so an agent can pass a name instead of SMILES ---
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


# ===========================================================================
# RDKit cheminformatics (run in minicrew/.venv; no conda env needed)
# ===========================================================================

@skill("ligand_descriptors",
       "Compute physicochemical descriptors (MW, logP, H-bond donors/acceptors, "
       "TPSA, rings, aromatic rings, rotatable bonds) for a ligand given a name "
       "or SMILES.",
       {"type": "object",
        "properties": {"ligand": {"type": "string",
                       "description": "ligand name (e.g. estradiol) or SMILES"}},
        "required": ["ligand"]})
def ligand_descriptors(ligand):
    from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors
    mol, smi = _mol(ligand)
    if mol is None:
        return {"error": f"could not parse {ligand!r}"}
    return {"input": ligand, "smiles": smi,
            "MW": round(Descriptors.MolWt(mol), 2),
            "logP": round(Crippen.MolLogP(mol), 2),
            "HBD": rdMolDescriptors.CalcNumHBD(mol),
            "HBA": rdMolDescriptors.CalcNumHBA(mol),
            "TPSA": round(rdMolDescriptors.CalcTPSA(mol), 1),
            "rings": rdMolDescriptors.CalcNumRings(mol),
            "aromatic_rings": rdMolDescriptors.CalcNumAromaticRings(mol),
            "rot_bonds": rdMolDescriptors.CalcNumRotatableBonds(mol)}


@skill("ligand_similarity",
       "Tanimoto (Morgan r2) similarity between two ligands (names or SMILES).",
       {"type": "object",
        "properties": {"ligand_a": {"type": "string"}, "ligand_b": {"type": "string"}},
        "required": ["ligand_a", "ligand_b"]})
def ligand_similarity(ligand_a, ligand_b):
    from rdkit.Chem import AllChem, DataStructs
    ma, _ = _mol(ligand_a)
    mb, _ = _mol(ligand_b)
    if ma is None or mb is None:
        return {"error": "could not parse one of the ligands"}
    fa = AllChem.GetMorganFingerprintAsBitVect(ma, 2, 2048)
    fb = AllChem.GetMorganFingerprintAsBitVect(mb, 2, 2048)
    return {"ligand_a": ligand_a, "ligand_b": ligand_b,
            "tanimoto": round(DataStructs.TanimotoSimilarity(fa, fb), 3)}


@skill("interaction_fingerprint",
       "ProLIF protein–ligand interaction fingerprint from a complex PDB: which "
       "protein residues contact the ligand and how (hydrophobic, H-bond, "
       "pi-stacking, …).",
       {"type": "object",
        "properties": {
            "pdb_path": {"type": "string",
                         "description": "path to a protein–ligand complex PDB (repo-relative ok)"},
            "ligand_resname": {"type": "string",
                               "description": "ligand residue name (default STR)"}},
        "required": ["pdb_path"]},
       requires={"allowed_input_roots": None})
def interaction_fingerprint(pdb_path, ligand_resname="STR"):
    abspath, err = safe_input_path(pdb_path)
    if err:
        return {"error": err}
    try:
        import MDAnalysis as mda
        import prolif as plf
        u = mda.Universe(abspath)
        lig_ag = u.select_atoms(f"resname {ligand_resname}")
        prot_ag = u.select_atoms("protein")
        if len(lig_ag) == 0:
            return {"error": f"no ligand with resname {ligand_resname!r} in {pdb_path}"}
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
    return {"pdb": os.path.basename(abspath), "ligand_resname": ligand_resname,
            "n_interacting_residues": len(summary), "interactions": summary}


@skill("train_model",
       "Train an XGBoost model on a CSV and report cross-validated performance + "
       "top feature importances. Give smiles_column to use RDKit descriptors as "
       "features; else numeric columns. Auto-detects classification vs regression.",
       {"type": "object",
        "properties": {
            "csv_path": {"type": "string", "description": "CSV path (repo-relative ok)"},
            "target_column": {"type": "string"},
            "smiles_column": {"type": "string",
                              "description": "optional; SMILES column to featurise with RDKit"}},
        "required": ["csv_path", "target_column"]})
def train_model(csv_path, target_column, smiles_column=None):
    import numpy as np
    import pandas as pd
    abspath, err = safe_input_path(csv_path)
    if err:
        return {"error": err}
    try:
        df = pd.read_csv(abspath)
    except Exception as exc:
        return {"error": f"could not read {csv_path}: {exc}"}
    if target_column not in df.columns:
        return {"error": f"target {target_column!r} not in columns {list(df.columns)}"}
    if smiles_column and smiles_column in df.columns:
        rows = [ligand_descriptors(s) for s in df[smiles_column]]
        feat = pd.DataFrame([{k: v for k, v in r.items()
                              if isinstance(v, (int, float))} for r in rows])
        feat_names, X = list(feat.columns), feat.values
    else:
        num = df.select_dtypes("number").drop(columns=[target_column], errors="ignore")
        feat_names, X = list(num.columns), num.values
    y_raw = df[target_column]
    n = len(df)
    classification = (y_raw.dtype == object) or (y_raw.nunique() <= 10 and y_raw.dtype != float)
    try:
        import xgboost as xgb
        from sklearn.metrics import accuracy_score, r2_score
        from sklearn.model_selection import cross_val_predict
        if classification:
            _, y = np.unique(y_raw, return_inverse=True)
            model = xgb.XGBClassifier(n_estimators=200, max_depth=3, verbosity=0,
                                      use_label_encoder=False)
            metric = "accuracy"
        else:
            y = y_raw.values.astype(float)
            model = xgb.XGBRegressor(n_estimators=200, max_depth=3, verbosity=0)
            metric = "R2"
        cv, score, note = min(5, n), None, ""
        if n >= 6 and cv >= 2:
            pred = cross_val_predict(model, X, y, cv=cv)
            score = accuracy_score(y, pred) if classification else r2_score(y, pred)
        else:
            note = f"only {n} rows — too few for CV; importances from a full fit"
        model.fit(X, y)
        imp = sorted(zip(feat_names, model.feature_importances_), key=lambda t: -t[1])[:8]
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


# ===========================================================================
# PyMOL structural analysis (subprocess into the pyrosetta conda env)
# ===========================================================================

@skill("analyze_structure",
       "Run real PyMOL on a protein–ligand complex (PDB/CIF, incl. Boltz/Protenix "
       "predictions): returns the ligand, pocket residues within a cutoff, and "
       "polar (H-bond-like) ligand–protein contacts with distances, plus a rendered "
       "pocket image. Use to inspect a predicted pose (which residues line the "
       "pocket, is the 3-keto/OH H-bonded, is the orientation sane).",
       {"type": "object",
        "properties": {
            "pdb_path": {"type": "string",
                         "description": "path to a complex PDB/CIF (repo-relative ok)"},
            "ligand_resname": {"type": "string",
                               "description": "ligand residue name; omit to auto-detect"},
            "pocket_cutoff": {"type": "number",
                              "description": "pocket radius in Å (default 5.0)"}},
        "required": ["pdb_path"]},
       requires={"binaries": ["pymol"], "conda_env": "pyrosetta",
                 "max_runtime_seconds": 180, "allow_network": False})
def analyze_structure(pdb_path, ligand_resname=None, pocket_cutoff=5.0, render=True):
    abspath, err = safe_input_path(pdb_path)
    if err:
        return {"error": err}
    if not os.path.exists(abspath):
        return {"error": f"file not found: {pdb_path}"}
    pymol = config.get("MINICREW_PYMOL_BIN",
                       os.path.expanduser("~/.conda/envs/pyrosetta/bin/pymol"))
    if not os.path.exists(pymol):
        return {"error": f"PyMOL not found at {pymol}; set MINICREW_PYMOL_BIN"}
    script = os.path.join(config.REPO_ROOT, "tfsensor", "pymol_analyze.py")
    out_png = ""
    if render:
        cache = os.path.join(config.REPO_ROOT, "data/ml/cache/pymol")
        os.makedirs(cache, exist_ok=True)
        base = os.path.splitext(os.path.basename(abspath))[0]
        out_png = os.path.join(cache, f"{base}_{ligand_resname or 'auto'}.png")
    args = [pymol, "-cq", script, "--", abspath,
            ligand_resname or "auto", str(pocket_cutoff), out_png]
    rs = run_subprocess(args, timeout=180)
    for line in rs["stdout"].splitlines():
        if "PYMOL_JSON:" in line:
            out = json.loads(line.split("PYMOL_JSON:", 1)[1])
            out["_provenance"] = {"command": " ".join(args), "binary": pymol,
                                  "input_files": [abspath],
                                  "output_files": [out_png] if out_png else []}
            return out
    return {"error": "no PyMOL output", "stderr": rs["stderr_tail"][-300:]}


@skill("pocket_mutation_view",
       "Show a mutation's effect on the pocket: threads the mutation(s) onto a "
       "holo complex (PyMOL mutagenesis rotamer swap) and renders the WT vs mutant "
       "pocket SIDE-BY-SIDE in the same view, mutated residues highlighted. Use to "
       "visualise steric/chemical changes (e.g. a D-ring clash). NOT energy-minimised.",
       {"type": "object",
        "properties": {
            "pdb_path": {"type": "string",
                         "description": "holo complex PDB/CIF (repo-relative ok)"},
            "mutations": {"type": "array", "items": {"type": "string"},
                          "description": "mutations to thread, e.g. ['I61L','L85I']"},
            "ligand_resname": {"type": "string",
                               "description": "ligand residue name; omit to auto-detect"}},
        "required": ["pdb_path", "mutations"]},
       requires={"binaries": ["pymol"], "conda_env": "pyrosetta",
                 "max_runtime_seconds": 600, "allow_network": False, "allow_write": True})
def pocket_mutation_view(pdb_path, mutations, ligand_resname=None):
    abspath, err = safe_input_path(pdb_path)
    if err:
        return {"error": err}
    if not os.path.exists(abspath):
        return {"error": f"file not found: {pdb_path}"}
    if not isinstance(mutations, list) or not mutations:
        return {"error": "mutations must be a non-empty list, e.g. ['I61L']"}
    pymol = config.get("MINICREW_PYMOL_BIN",
                       os.path.expanduser("~/.conda/envs/pyrosetta/bin/pymol"))
    if not os.path.exists(pymol):
        return {"error": f"PyMOL not found at {pymol}; set MINICREW_PYMOL_BIN"}
    cache = os.path.join(config.REPO_ROOT, "data/ml/cache/pymol")
    os.makedirs(cache, exist_ok=True)
    base = os.path.splitext(os.path.basename(abspath))[0]
    tag = "_".join(mutations)
    mut_pdb = os.path.join(cache, f"{base}_{tag}.pdb")

    # 1) thread the mutation(s) with PyRosetta (headless PyMOL mutagenesis is broken)
    t = run_subprocess([conda_python("pyrosetta"), "-m", "tfsensor.thread_mutant",
                        abspath, ",".join(mutations), mut_pdb],
                       timeout=600, cwd=config.REPO_ROOT,
                       env_extra={"PYTHONPATH": config.REPO_ROOT})
    if not os.path.exists(mut_pdb):
        return {"error": f"threading failed (rc={t['rc']})", "stderr": t["stderr_tail"][-400:]}
    thread_info = {}
    for line in t["stdout"].splitlines():
        if "THREAD_JSON:" in line:
            thread_info = json.loads(line.split("THREAD_JSON:", 1)[1])

    # 2) render WT + mutant pockets with the proven pymol_analyze script
    script = os.path.join(config.REPO_ROOT, "tfsensor", "pymol_analyze.py")

    def _render(pdb_in, png):
        a = [pymol, "-cq", script, "--", pdb_in, ligand_resname or "auto", "5.0", png]
        rs = run_subprocess(a, timeout=200)
        for line in rs["stdout"].splitlines():
            if "PYMOL_JSON:" in line:
                return json.loads(line.split("PYMOL_JSON:", 1)[1])
        return {"error": "no PyMOL output", "stderr": rs["stderr_tail"][-200:]}

    wt_png = os.path.join(cache, f"{base}_wt.png")
    mut_png = os.path.join(cache, f"{base}_{tag}_mut.png")
    wt = _render(abspath, wt_png)
    mut = _render(mut_pdb, mut_png)

    def _ckeys(rep):
        return {(c["residue"], c["ligand_atom"]) for c in (rep.get("polar_contacts") or [])}
    lost = sorted(f"{r} · {a}" for r, a in _ckeys(wt) - _ckeys(mut))
    gained = sorted(f"{r} · {a}" for r, a in _ckeys(mut) - _ckeys(wt))
    mism = thread_info.get("mismatches") or []

    return {"summary": f"WT vs {'+'.join(mutations)} pocket"
            + (f" — {len(lost)} contact(s) lost, {len(gained)} gained" if (lost or gained) else "")
            + ("; WT-IDENTITY MISMATCH" if mism else ""),
            "metrics": {"mutations": "+".join(mutations),
                        "wt_polar_contacts": wt.get("n_polar_contacts"),
                        "mut_polar_contacts": mut.get("n_polar_contacts"),
                        "applied": thread_info.get("applied")},
            "contacts_lost": lost, "contacts_gained": gained,
            "wt_pocket_residues": wt.get("pocket_residues"),
            "mut_pocket_residues": mut.get("pocket_residues"),
            "_artifacts": [{"type": "image", "uri": wt_png, "caption": "WT pocket"},
                           {"type": "image", "uri": mut_png,
                            "caption": "+".join(mutations) + " pocket"}],
            "_provenance": {"input_files": [abspath], "output_files": [mut_pdb, wt_png, mut_png]},
            "_warnings": (["WT-identity mismatch: " + "; ".join(mism)] if mism else [])
            + ["mutant side-chains placed by PyRosetta MutateResidue (rotamer, not "
               "full repack/minimise) — shows placement, not the relaxed pose"]}


# ===========================================================================
# flex-ddG scoring (subprocess: tfsensor.design_score worker, pyrosetta env)
# ===========================================================================

@skill("flexddg_score",
       "Estimate the interface binding energy of a (multi-)mutant for one steroid "
       "via flex-ddG (PyRosetta): threads the mutation(s) onto a holo pose, "
       "flex-relaxes, and reports dG_separated and ΔΔG vs WT. NOTE: binding-ΔΔG is "
       "a COARSE ranker — see the computational-boundary note; do not gate "
       "selectivity on a ~1 kcal/mol margin.",
       {"type": "object",
        "properties": {
            "pdb_path": {"type": "string",
                         "description": "holo complex pose (PDB/CIF, repo-relative ok)"},
            "mutations": {"type": "array", "items": {"type": "string"},
                          "description": "model-numbering mutations, e.g. ['I61L','L85I']"},
            "ligand": {"type": "string",
                       "description": "steroid name in data/steroid_panel.csv (default testosterone)"},
            "seed": {"type": "string", "description": "PyRosetta seed (default '1')"}},
        "required": ["pdb_path", "mutations"]},
       requires={"conda_env": "pyrosetta", "max_runtime_seconds": 1800,
                 "allow_network": False, "allow_write": True})
def flexddg_score(pdb_path, mutations, ligand="testosterone", seed="1"):
    pose, err = safe_input_path(pdb_path)
    if err:
        return {"error": err}
    if not os.path.exists(pose):
        return {"error": f"file not found: {pdb_path}"}
    if not isinstance(mutations, list) or not mutations:
        return {"error": "mutations must be a non-empty list, e.g. ['I61L']"}
    rid = run_id()
    wd = os.path.join(config.REPO_ROOT, "minicrew", "artifacts", rid)
    os.makedirs(wd, exist_ok=True)
    lib = os.path.join(wd, "design.json")
    oj = os.path.join(wd, "out.json")
    json.dump([{"id": "design", "n_mut": len(mutations), "mutations": mutations}],
              open(lib, "w"))
    panel = os.path.join(config.REPO_ROOT, "data", "steroid_panel.csv")
    cmd = [conda_python("pyrosetta"), "-m", "tfsensor.design_score", "worker",
           "--ligand", ligand, "--seed", str(seed), "--designs", lib,
           "--panel", panel, "--work_dir", wd, "--out_json", oj, "--holo_pdb", pose]
    rs = run_subprocess(cmd, timeout=1800, cwd=config.REPO_ROOT,
                        env_extra={"PYTHONPATH": config.REPO_ROOT})
    if not os.path.exists(oj):
        return {"error": f"flex-ddG produced no output (rc={rs['rc']}, "
                f"timed_out={rs['timed_out']})", "stderr": rs["stderr_tail"][-400:]}
    o = json.load(open(oj))
    d = o.get("designs", {}).get("design", {})
    return {"summary": f"{'+'.join(mutations)} vs {ligand}: dG={d.get('dG')} "
            f"ddG_vs_wt={d.get('ddG_vs_wt')}",
            "metrics": {"dG": d.get("dG"), "ddG_vs_wt": d.get("ddG_vs_wt"),
                        "dG_wt": o.get("dG_wt"), "ligand": ligand},
            "_provenance": {"command": " ".join(cmd), "input_files": [pose],
                            "output_files": [oj]},
            "_stderr_tail": rs["stderr_tail"][-400:],
            "_warnings": ["binding-ΔΔG is a coarse ranker; one pose, one relax — "
                          "not a selectivity verdict (see COMPUTATIONAL_BOUNDARY.md)"]}


@skill("boltz_compare",
       "Fold WT vs mutant holo complex with Boltz-2 and compare POCKET + BINDING: "
       "returns each one's affinity_probability_binary (binding head), the holo DBD "
       "spacing (Å), and a rendered mutant pocket. LONG-RUNNING (GPU, ~5-15 min for "
       "two folds). Caveat: DL poses flip the steroid A-ring (~1/15 SAR-consistent) "
       "and single-structure opening doesn't predict amplitude — treat as COARSE "
       "structural evidence, not a binding/activation verdict (COMPUTATIONAL_BOUNDARY.md).",
       {"type": "object",
        "properties": {
            "mutations": {"type": "array", "items": {"type": "string"},
                          "description": "model-numbering mutations, e.g. ['I61L','L85I']"},
            "ligand": {"type": "string",
                       "description": "steroid in data/steroid_panel.csv (default testosterone)"},
            "seed": {"type": "number", "description": "Boltz seed (default 1)"}},
        "required": ["mutations"]},
       requires={"max_runtime_seconds": 2400, "allow_network": True,
                 "allow_write": True})   # boltz binary checked in-body (it's a venv exe)
def boltz_compare(mutations, ligand="testosterone", seed=1):
    import csv as _csv
    from tfsensor import boltz_holo_inputs as bhi
    from tfsensor.ml.bo.seed import parse_mutation
    try:
        from tfsensor.rescore_oriented import _dbd
    except Exception:
        _dbd = None
    if not isinstance(mutations, list) or not mutations:
        return {"error": "mutations must be a non-empty list, e.g. ['I61L']"}
    boltz = config.get("TFSENSOR_BOLTZ_BIN", "")
    if not boltz or not os.path.exists(boltz):
        return {"error": f"Boltz binary not found ({boltz}); set TFSENSOR_BOLTZ_BIN"}
    panel = os.path.join(config.REPO_ROOT, "data", "steroid_panel.csv")
    smiles = {r["name"].strip(): r["smiles"].strip() for r in _csv.DictReader(open(panel))}
    if ligand not in smiles:
        return {"error": f"ligand {ligand!r} not in panel {sorted(smiles)}"}
    seq = bhi._read_first_chain(os.path.join(config.REPO_ROOT, "data", "AcrR_dimer.fasta"))
    # 'I61L' -> '61:L' for boltz_holo_inputs._apply_mutations
    try:
        muts_pa = [f"{parse_mutation(m)[1]}:{parse_mutation(m)[2]}" for m in mutations]
    except Exception as exc:
        return {"error": f"bad mutation token: {exc}"}

    rid = run_id()
    work = os.path.join(config.REPO_ROOT, "minicrew", "artifacts", rid, "boltz")
    out = {}
    for label, s in (("wt", seq), ("mut", bhi._apply_mutations(seq, muts_pa))):
        ind = os.path.join(work, f"{label}_in")
        os.makedirs(ind, exist_ok=True)
        job = f"{label}_{ligand}"
        bhi.build_holo_yaml(os.path.join(ind, f"{job}.yaml"), s, smiles[ligand])
        odir = os.path.join(work, f"{label}_out")
        cmd = [boltz, "predict", ind, "--out_dir", odir, "--seed", str(int(seed)),
               "--diffusion_samples", "1", "--recycling_steps", "3", "--model", "boltz2",
               "--output_format", "pdb", "--devices", "1", "--accelerator", "gpu",
               "--use_msa_server"]
        rs = run_subprocess(cmd, timeout=1200, cwd=config.REPO_ROOT)
        import glob
        pdbs = glob.glob(os.path.join(odir, "**", "predictions", job, f"{job}_model_0.pdb"),
                         recursive=True)
        affs = glob.glob(os.path.join(odir, "**", "predictions", job, f"affinity_{job}.json"),
                         recursive=True)
        rec = {"rc": rs["rc"]}
        if pdbs:
            rec["pdb"] = pdbs[0]
            if _dbd:
                try:
                    rec["dbd_spacing_A"] = round(_dbd(pdbs[0]), 2)
                except Exception:
                    rec["dbd_spacing_A"] = None
        if affs:
            try:
                rec["affinity_probability_binary"] = round(
                    json.load(open(affs[0])).get("affinity_probability_binary"), 3)
            except Exception:
                pass
        out[label] = rec
        if label == "wt" and "pdb" not in rec:
            return {"error": f"Boltz WT fold produced no model (rc={rs['rc']})",
                    "stderr": rs["stderr_tail"][-400:]}

    arts = []
    mut_pdb = out.get("mut", {}).get("pdb")
    if mut_pdb:
        png = os.path.join(work, f"mut_{ligand}_pocket.png")
        a = [config.get("MINICREW_PYMOL_BIN", os.path.expanduser("~/.conda/envs/pyrosetta/bin/pymol")),
             "-cq", os.path.join(config.REPO_ROOT, "tfsensor", "pymol_analyze.py"),
             "--", mut_pdb, "auto", "5.0", png]
        run_subprocess(a, timeout=200)
        if os.path.exists(png):
            arts.append({"type": "image", "uri": png, "caption": f"{'+'.join(mutations)} holo pocket (Boltz)"})

    wt, mut = out.get("wt", {}), out.get("mut", {})
    return {"summary": f"Boltz WT vs {'+'.join(mutations)} ({ligand}): "
            f"affinity {wt.get('affinity_probability_binary')}→{mut.get('affinity_probability_binary')}, "
            f"DBD {wt.get('dbd_spacing_A')}→{mut.get('dbd_spacing_A')} Å",
            "metrics": {"wt_affinity": wt.get("affinity_probability_binary"),
                        "mut_affinity": mut.get("affinity_probability_binary"),
                        "wt_dbd_A": wt.get("dbd_spacing_A"),
                        "mut_dbd_A": mut.get("dbd_spacing_A"), "ligand": ligand},
            "wt": wt, "mut": mut, "_artifacts": arts,
            "_warnings": ["Boltz flips the steroid A-ring often (SAR-check the pose); "
                          "single-structure DBD spacing ≠ activation amplitude; 1 "
                          "diffusion sample — coarse structural evidence only"]}


@skill("literature_search",
       "Search the web literature (Semantic Scholar or OpenAlex — open APIs, no "
       "key) for papers on a topic: returns title, authors, year, venue, DOI, "
       "citation count, abstract, and URL. Use to find external evidence / "
       "precedents; pair with `distill` to store a vetted note. Abstracts only "
       "(not full text); verify claims against the source before trusting.",
       {"type": "object",
        "properties": {
            "query": {"type": "string", "description": "search query (keywords/phrase)"},
            "limit": {"type": "number", "description": "max papers (default 8)"},
            "source": {"type": "string",
                       "description": "openalex (default) | semantic_scholar"},
            "year_from": {"type": "number", "description": "optional earliest year"}},
        "required": ["query"]},
       requires={"allow_network": True, "max_runtime_seconds": 60})
def literature_search(query, limit=8, source="openalex", year_from=None):
    limit = max(1, min(int(limit), 25))
    # try the requested source, then fall back to the other (S2 rate-limits w/o a key)
    order = [source] + [s for s in ("openalex", "semantic_scholar") if s != source]
    errs = []
    for src in order:
        try:
            papers = (_search_openalex if src == "openalex" else _search_s2)(query, limit, year_from)
            return {"summary": f"{len(papers)} papers for {query!r} via {src}",
                    "metrics": {"n": len(papers), "source": src},
                    "query": query, "papers": papers,
                    "_warnings": ([f"{source} failed, used {src}"] if src != source else [])}
        except Exception as exc:
            errs.append(f"{src}: {exc}")
    return {"error": "literature search failed — " + " | ".join(errs)}


def _search_openalex(query, limit, year_from):
    import requests
    params = {"search": query, "per-page": limit,
              "select": "title,publication_year,authorships,doi,primary_location,"
                        "cited_by_count,abstract_inverted_index"}
    if year_from:
        params["filter"] = f"from_publication_date:{int(year_from)}-01-01"
    r = requests.get("https://api.openalex.org/works", params=params, timeout=45)
    r.raise_for_status()
    return [_openalex_paper(w) for w in r.json().get("results", [])]


def _search_s2(query, limit, year_from):
    import requests
    params = {"query": query, "limit": limit,
              "fields": "title,abstract,year,venue,citationCount,externalIds,url,authors.name"}
    if year_from:
        params["year"] = f"{int(year_from)}-"
    r = requests.get("https://api.semanticscholar.org/graph/v1/paper/search",
                     params=params, timeout=45)
    r.raise_for_status()
    return [_s2_paper(p) for p in r.json().get("data", [])]


def _s2_paper(p):
    ext = p.get("externalIds") or {}
    return {"title": p.get("title"), "year": p.get("year"),
            "authors": [a.get("name") for a in (p.get("authors") or [])][:6],
            "venue": p.get("venue"), "doi": ext.get("DOI"),
            "citations": p.get("citationCount"), "url": p.get("url"),
            "abstract": (p.get("abstract") or "")[:1200]}


def _openalex_paper(w):
    abs_idx = w.get("abstract_inverted_index") or {}
    abstract = ""
    if abs_idx:
        words = sorted(((pos, wd) for wd, ps in abs_idx.items() for pos in ps))
        abstract = " ".join(wd for _, wd in words)[:1200]
    loc = (w.get("primary_location") or {}).get("source") or {}
    return {"title": w.get("title"), "year": w.get("publication_year"),
            "authors": [a["author"]["display_name"]
                        for a in (w.get("authorships") or [])][:6],
            "venue": loc.get("display_name"),
            "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
            "citations": w.get("cited_by_count"), "url": w.get("doi"),
            "abstract": abstract}


@skill("retrodict",
       "Run the orientation-corrected flex-ddG retrodiction benchmark "
       "(tfsensor.ml.bo.retrodict): scores WT + known singles on SAR-consistent "
       "poses and checks WT steroid order + per-single selectivity shift vs the "
       "empirical scan. LONG-RUNNING (many flex-ddG workers). Returns the verdict.",
       {"type": "object",
        "properties": {"jobs": {"type": "number", "description": "parallel workers (default 6)"}},
        "required": []},
       requires={"conda_env": "pyrosetta", "max_runtime_seconds": 5400,
                 "allow_network": False, "allow_write": True})
def retrodict(jobs=6):
    out = os.path.join(config.REPO_ROOT, "results", "stage4_bo", "retrodiction.json")
    cmd = [conda_python("pyrosetta"), "-m", "tfsensor.ml.bo.retrodict",
           "--jobs", str(int(jobs)), "--out_json", out]
    rs = run_subprocess(cmd, timeout=5400, cwd=config.REPO_ROOT,
                        env_extra={"PYTHONPATH": config.REPO_ROOT})
    if not os.path.exists(out):
        return {"error": f"retrodict produced no output (rc={rs['rc']}, "
                f"timed_out={rs['timed_out']})", "stderr": rs["stderr_tail"][-400:]}
    r = json.load(open(out))
    return {"summary": f"retrodiction {'PASS' if r.get('PASS') else 'FAIL'} — "
            f"WT order {'ok' if r.get('wt_order_ok') else 'fail'}, "
            f"bias {'ok' if r.get('bias_ok') else 'fail'}",
            "metrics": {"PASS": r.get("PASS"), "wt_order_ok": r.get("wt_order_ok"),
                        "bias_ok": r.get("bias_ok")},
            "verdict": r,
            "_provenance": {"command": " ".join(cmd), "output_files": [out]},
            "_stderr_tail": rs["stderr_tail"][-400:]}
