"""Stage-3a ΔΔG orchestrator: run the fixed-backbone ΔΔG worker across the panel.

Spawns one ddg_mutation worker subprocess per (ligand, seed-backbone) — a subprocess
because pyrosetta.init is one-shot per process — runs up to --jobs in parallel (PyRosetta
is CPU-bound), then aggregates ΔΔG per (mutation, ligand) as mean ± sd across seeds.

    python -m tfsensor.ddg_panel --panel data/steroid_panel.csv \
        --boltz_root results/stage1_wt_validation/boltz --seeds 1,42,2024 \
        --mutations R123E,R123D,F119W,L147R --n_replicates 3 --jobs 8 \
        --work_root results/stage3_ddg/work --out_json results/stage3_ddg/ddg_results.json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time

from tfsensor.physics_panel import _load_panel, _top_boltz_pose


def _launch(holo, smiles, ligand, seed, mutations, work_dir, n_ens):
    os.makedirs(work_dir, exist_ok=True)
    out_json = os.path.join(work_dir, "ddg.json")
    log = open(os.path.join(work_dir, "worker.log"), "w")
    cmd = [sys.executable, "-m", "tfsensor.ddg_mutation",
           "--holo_pdb", holo, "--smiles", smiles, "--ligand", ligand,
           "--seed", str(seed), "--mutations", ",".join(mutations),
           "--n_ensemble", str(n_ens), "--work_dir", work_dir, "--out_json", out_json]
    p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    return {"proc": p, "log": log, "out_json": out_json,
            "ligand": ligand, "seed": seed, "work_dir": work_dir}


def run(panel_csv, boltz_root, seeds, mutations, work_root, out_json, n_ens,
        jobs=8, prefix="wt"):
    target, decoys, smiles = _load_panel(panel_csv)
    ligands = [target] + decoys
    work_root = os.path.abspath(work_root)

    jobs_list = []
    for seed in seeds:
        for lig in ligands:
            pose = _top_boltz_pose(boltz_root, seed, lig, prefix)
            if not pose:
                print(f"[warn] no pose: {lig} seed{seed}")
                continue
            jobs_list.append((pose, smiles[lig], lig, seed))

    running, done = [], []
    i = 0
    while i < len(jobs_list) or running:
        while len(running) < jobs and i < len(jobs_list):
            pose, smi, lig, seed = jobs_list[i]
            wd = os.path.join(work_root, f"seed{seed}", lig)
            print(f"[launch] {lig} seed{seed}", flush=True)
            running.append(_launch(pose, smi, lig, seed, mutations, wd, n_ens))
            i += 1
        time.sleep(5)
        for h in running[:]:
            if h["proc"].poll() is not None:
                h["log"].close()
                ok = h["proc"].returncode == 0 and os.path.exists(h["out_json"])
                print(f"[done {'OK' if ok else 'FAIL'}] {h['ligand']} seed{h['seed']}",
                      flush=True)
                done.append(h)
                running.remove(h)

    # ---- aggregate ----
    raw = {}
    for h in done:
        if os.path.exists(h["out_json"]):
            raw.setdefault(h["seed"], {})[h["ligand"]] = json.load(open(h["out_json"]))

    ddg = {}
    for mut in mutations:
        ddg[mut] = {}
        for lig in ligands:
            vals = []
            for s in seeds:
                rec = raw.get(s, {}).get(lig, {}).get("ddg", {}).get(mut, {})
                if rec.get("value") is not None:
                    vals.append(rec["value"])
            if vals:
                ddg[mut][lig] = {
                    "mean": round(statistics.mean(vals), 3),
                    "sd": round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0,
                    "per_seed": vals, "n_seeds": len(vals)}

    out = {"metric": "rosetta_flex_ddG_bind (pre-relax + backrub-style ensemble, paired, median)",
           "sign_convention": "ddG<0 = mutation strengthens binding (lower dG_separated)",
           "seeds": seeds, "n_ensemble": n_ens, "ligands": ligands, "target": target,
           "ddg": ddg}
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    json.dump(out, open(out_json, "w"), indent=2)

    # console table
    print("\n==== ΔΔG_bind (kcal/mol; <0 = mutation strengthens binding) ====")
    for mut in mutations:
        print(f"\n{mut}:")
        for lig in ligands:
            d = ddg[mut].get(lig)
            if d:
                print(f"  {lig:13s} ΔΔG = {d['mean']:+6.2f} ± {d['sd']:.2f}  "
                      f"(per-seed {d['per_seed']})")
    print(f"\n[ddg_panel] wrote {out_json}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panel", required=True)
    ap.add_argument("--boltz_root", required=True)
    ap.add_argument("--seeds", default="1,42,2024")
    ap.add_argument("--mutations", default="R123E,R123D,F119W,L147R")
    ap.add_argument("--n_ensemble", type=int, default=8)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--work_root", required=True)
    ap.add_argument("--out_json", required=True)
    ap.add_argument("--prefix", default="wt")
    args = ap.parse_args()
    seeds = [s.strip() for s in args.seeds.split(",") if s.strip()]
    mutations = [m.strip() for m in args.mutations.split(",") if m.strip()]
    run(args.panel, args.boltz_root, seeds, mutations, args.work_root,
        args.out_json, args.n_ensemble, args.jobs, args.prefix)


if __name__ == "__main__":
    main()
