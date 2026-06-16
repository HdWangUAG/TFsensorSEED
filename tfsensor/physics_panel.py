"""Stage-1b physics arbiter: seed-averaged Rosetta interface dG across the panel.

The two DL affinity/confidence heads (Boltz binder-prob, Protenix ligand-ipTM)
oversmooth on the near-isosteric steroid panel and fail to reproduce the
experimental WT *estradiol preference* (Stage-1 dual NO-GO). The plan's Track-B
remedy is a physics interface energy on the predicted holo pose. This driver runs
``physics_score.interface_dg`` (PyRosetta InterfaceAnalyzer ``dG_separated``,
constrained-relaxed) on the top predicted pose for every steroid x seed, then
seed-averages and asks: does the physics dG rank estradiol below (= stronger than)
the decoys it must reject?

Lower dG = stronger predicted binding, so for a "target wins" call we want
estradiol to have the *most negative* mean dG and a negative margin
``dG(estradiol) - min(dG(decoys))``.

Run in the pyrosetta env (pyrosetta + rdkit):
    python -m tfsensor.physics_panel \
        --panel data/steroid_panel.csv \
        --boltz_root results/stage1_wt_validation/boltz \
        --seeds 1,42,2024 \
        --work_root results/stage1b_physics/work \
        --out_json results/stage1b_physics/physics_go_nogo.json
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import statistics
import subprocess
import sys


def _load_panel(panel_csv):
    target, decoys, smiles = None, [], {}
    with open(panel_csv) as fh:
        for row in csv.DictReader(fh):
            smiles[row["name"]] = row["smiles"]
            if row["role"] == "target":
                target = row["name"]
            else:
                decoys.append(row["name"])
    return target, decoys, smiles


def _top_boltz_pose(boltz_root, seed, name, prefix="wt"):
    """Top-ranked Boltz model PDB for steroid `name` at `seed` (model_0)."""
    job = f"{prefix}_{name}"
    patt = os.path.join(
        boltz_root, f"seed{seed}", "boltz_results_inputs", "predictions",
        job, f"{job}_model_0.pdb")
    hits = glob.glob(patt)
    return hits[0] if hits else None


def _dg_subprocess(pose, smiles, name, work_dir, relax_cycles):
    """Run physics_score in a fresh process so PyRosetta re-inits per ligand.

    PyRosetta's ``init`` is one-shot per process, so a single process can only
    register one ligand's ``-extra_res_fa`` params; looping in-process makes every
    ligand after the first an "unrecognized residue". A subprocess per pose avoids
    that entirely. Returns the result dict, or None on failure.
    """
    os.makedirs(work_dir, exist_ok=True)
    out_json = os.path.join(work_dir, "dg.json")
    cmd = [sys.executable, "-m", "tfsensor.physics_score",
           "--holo_pdb", pose, "--smiles", smiles, "--name", name,
           "--work_dir", work_dir, "--relax_cycles", str(relax_cycles),
           "--out_json", out_json]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not os.path.exists(out_json):
        print(f"[warn] physics_score failed for {name}:\n{proc.stderr[-800:]}")
        return None
    return json.load(open(out_json))


def run_panel(panel_csv, boltz_root, seeds, work_root, out_json, relax_cycles=1,
              prefix="wt"):
    target, decoys, smiles = _load_panel(panel_csv)
    names = [target] + decoys
    # molfile_to_params runs with cwd=work_dir and resolves the .mol path against
    # it, so work dirs must be absolute (relative paths double up under the cwd).
    work_root = os.path.abspath(work_root)
    os.makedirs(work_root, exist_ok=True)

    per_seed = {}
    for seed in seeds:
        per_seed[seed] = {}
        for name in names:
            pose = _top_boltz_pose(boltz_root, seed, name, prefix)
            if pose is None:
                print(f"[warn] no pose: seed {seed} {name}")
                continue
            wd = os.path.join(work_root, f"seed{seed}", name)
            res = _dg_subprocess(pose, smiles[name], name, wd, relax_cycles)
            if res is None:
                continue
            per_seed[seed][name] = round(res["dG_separated"], 3)
            print(f"[seed {seed}] {name:13s} dG = {res['dG_separated']:.2f}", flush=True)

    # seed-averaged dG per steroid (lower = stronger binding)
    mean_dg = {}
    for name in names:
        vals = [per_seed[s][name] for s in seeds if name in per_seed[s]]
        if vals:
            mean_dg[name] = round(statistics.mean(vals), 3)

    # per-seed: does estradiol beat (have lower dG than) ALL decoys?
    seed_target_wins = 0
    seed_target_is_top = 0
    margins = []
    for s in seeds:
        sc = per_seed[s]
        if target not in sc:
            continue
        decoy_dgs = [sc[d] for d in decoys if d in sc]
        if not decoy_dgs:
            continue
        best_decoy = min(decoy_dgs)               # strongest decoy = lowest dG
        margin = round(sc[target] - best_decoy, 3)  # <0 means target stronger
        margins.append(margin)
        beats_all = all(sc[target] < sc[d] for d in decoys if d in sc)
        is_top = sc[target] == min(sc.values())
        seed_target_wins += int(beats_all)
        seed_target_is_top += int(is_top)

    n = len([s for s in seeds if target in per_seed[s]])
    out = {
        "metric": "rosetta_interface_dG_separated",
        "higher_is_better": False,
        "target": target,
        "decoys": decoys,
        "n_seeds": n,
        "seeds_target_beats_all_decoys": seed_target_wins,
        "seeds_target_is_top": seed_target_is_top,
        "margin_mean": round(statistics.mean(margins), 4) if margins else None,
        "margin_min": round(min(margins), 4) if margins else None,
        "margin_all_negative": bool(margins) and all(m < 0 for m in margins),
        "mean_dG_per_ligand": mean_dg,
        "per_seed": per_seed,
        "GO": bool(margins) and seed_target_wins == n and n > 0,
    }
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    json.dump(out, open(out_json, "w"), indent=2)
    print(json.dumps(out, indent=2))
    verdict = "GO" if out["GO"] else "NO-GO"
    print(f"\n[physics] GO/NO-GO = {verdict}  "
          f"({target} stronger than all decoys in "
          f"{seed_target_wins}/{n} seeds; margin mean {out['margin_mean']})")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panel", required=True)
    ap.add_argument("--boltz_root", required=True)
    ap.add_argument("--seeds", default="1,42,2024")
    ap.add_argument("--work_root", required=True)
    ap.add_argument("--out_json", required=True)
    ap.add_argument("--relax_cycles", type=int, default=1)
    ap.add_argument("--prefix", default="wt",
                    help="Boltz job prefix (wt / f119w / l147r) -> finds <prefix>_<ligand>")
    args = ap.parse_args()
    seeds = [s.strip() for s in args.seeds.split(",") if s.strip()]
    run_panel(args.panel, args.boltz_root, seeds, args.work_root,
              args.out_json, args.relax_cycles, args.prefix)


if __name__ == "__main__":
    main()
