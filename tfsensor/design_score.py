"""Stage-3 Tier-1: flex-ddG specificity screen of LigandMPNN designs.

For each design (a full pocket sequence vs WT) and each steroid, thread the design's
mutations onto the pre-relaxed WT holo backbone (both homodimer chains), flex-relax
locally (backbone-flexible shell + tethered ligand), and score dG_separated. Rank by
RELATIVE SPECIFICITY for estradiol:
    margin(design) = dG(estradiol) - min(dG decoys)   [strongly negative = estradiol-specific]
Also reports ΔΔG vs WT per ligand. Reuses the calibrated ddg_mutation machinery.

Cost control: the broad screen uses 1 backbone + 1 relax/design/ligand (cheap); the
Top-N then go to the full ensemble + two-state gate. Designs are SHARDED across worker
subprocesses (one pyrosetta.init per worker) for parallelism.

  worker: python -m tfsensor.design_score worker --ligand estradiol --seed 1 \
              --designs <shard.json> --out_json <out.json>
  panel:  python -m tfsensor.design_score panel --library results/stage3_design/library.json \
              --seeds 1 --jobs 32 --shards 8 --top 20 \
              --work_root results/stage3_design/screen --out_json results/stage3_design/screen.json
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import glob
import json
import os
import statistics
import subprocess
import sys

from tfsensor.ddg_mutation import (_build_complex, _prerelax, _relax, _interface_dg,
                                    _tether_ligand, _ligand_residue_index, CHAINS)
from tfsensor.ligandmpnn_gen import POCKET as POCKET_FOCUS
from tfsensor.physics_panel import _load_panel, _top_boltz_pose

ONE2THREE = {"A": "ALA", "R": "ARG", "N": "ASN", "D": "ASP", "C": "CYS", "Q": "GLN",
             "E": "GLU", "G": "GLY", "H": "HIS", "I": "ILE", "L": "LEU", "K": "LYS",
             "M": "MET", "F": "PHE", "P": "PRO", "S": "SER", "T": "THR", "W": "TRP",
             "Y": "TYR", "V": "VAL"}


def _thread(pose, mutations):
    """Apply mutations like 'I61L' to BOTH homodimer chains (symmetric design)."""
    from pyrosetta.rosetta.protocols.simple_moves import MutateResidue
    for mut in mutations:
        pos = int(mut[1:-1]); to3 = ONE2THREE[mut[-1]]
        for c in CHAINS:
            idx = pose.pdb_info().pdb2pose(c, pos)
            if idx:
                MutateResidue(idx, to3).apply(pose)


def cmd_worker(args):
    designs = json.load(open(args.designs))
    panel = dict((r["name"], r["smiles"]) for r in __import__("csv").DictReader(
        open(args.panel)))
    smiles = panel[args.ligand]
    work = os.path.abspath(args.work_dir)
    os.makedirs(work, exist_ok=True)
    holo = _top_boltz_pose(args.boltz_root, args.seed, args.ligand, "wt")
    params, complex_pdb = _build_complex(holo, smiles, args.ligand, work)

    import pyrosetta
    pyrosetta.init(f"-extra_res_fa {params} -mute all -ignore_unrecognized_res false "
                   f"-ex1 -ex2 -use_input_sc -run:constant_seed -jran {args.seed}")
    base = pyrosetta.pose_from_file(complex_pdb)
    sf = pyrosetta.get_fa_scorefxn()
    sf.set_weight(pyrosetta.rosetta.core.scoring.coordinate_constraint, 1.0)
    lig_idx = _ligand_residue_index(base)

    wt_clean = base.clone()
    _prerelax(wt_clean, sf, lig_idx)
    dg_wt = _interface_dg(wt_clean)
    # design shell = all pocket positions both chains + ligand
    focus = [wt_clean.pdb_info().pdb2pose(c, p) for c in CHAINS for p in POCKET_FOCUS]
    focus = [i for i in focus if i] + [lig_idx]

    out = {"ligand": args.ligand, "seed": args.seed, "dG_wt": round(dg_wt, 3), "designs": {}}
    for d in designs:
        p = wt_clean.clone()
        _thread(p, d["mutations"])
        _tether_ligand(p, lig_idx)
        _relax(p, sf, focus, lig_idx, bb_flex=True)
        dg = _interface_dg(p)
        out["designs"][d["id"]] = {"dG": round(dg, 3), "ddG_vs_wt": round(dg - dg_wt, 3)}
        print(f"[score] {args.ligand} s{args.seed} {d['id']} dG={dg:.2f}", flush=True)
    json.dump(out, open(args.out_json, "w"), indent=2)


def _run_worker(item, args):
    """Launch one scoring worker subprocess (blocking). Runs inside a thread of the
    pool; the heavy lifting is in the child process, the thread just waits on it."""
    lig, s, i, sf = item
    wd = os.path.join(os.path.abspath(args.work_root), f"{lig}_s{s}_sh{i}")
    os.makedirs(wd, exist_ok=True)
    oj = os.path.join(wd, "out.json")
    cmd = [sys.executable, "-m", "tfsensor.design_score", "worker",
           "--ligand", lig, "--seed", s, "--designs", sf,
           "--panel", args.panel, "--boltz_root", args.boltz_root,
           "--work_dir", wd, "--out_json", oj]
    with open(os.path.join(wd, "log"), "w") as log:
        rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
    return {"item": item, "oj": oj, "rc": rc}


def cmd_panel(args):
    # Stage-3 DESIGN target = estradiol (engineering goal), NOT the panel-CSV role
    # (which is testosterone, set during WT validation). Decoys = the other three.
    pt, pd, _ = _load_panel(args.panel)
    ligands = [pt] + pd
    target = args.target
    assert target in ligands, f"target {target} not in panel {ligands}"
    decoys = [l for l in ligands if l != target]
    rival = getattr(args, "rival", None) or None
    seeds = [s.strip() for s in args.seeds.split(",") if s.strip()]
    lib = json.load(open(args.library))
    work_root = os.path.abspath(args.work_root)
    os.makedirs(work_root, exist_ok=True)

    # shard designs
    S = args.shards
    shards = [lib[i::S] for i in range(S)]
    shard_files = []
    for i, sh in enumerate(shards):
        f = os.path.join(work_root, f"shard_{i}.json")
        json.dump(sh, open(f, "w"))
        shard_files.append(f)

    # work items: (ligand, seed, shard); scheduled across a bounded thread pool,
    # one subprocess worker per item, up to args.jobs concurrently.
    items = [(lig, s, i, sf) for lig in ligands for s in seeds
             for i, sf in enumerate(shard_files)]
    done = []
    with cf.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = [ex.submit(_run_worker, it, args) for it in items]
        for n, fut in enumerate(cf.as_completed(futs), 1):
            res = fut.result()
            done.append(res)
            tag = "ok" if res["rc"] == 0 else f"rc={res['rc']}"
            if res["rc"] != 0:
                print(f"[panel][warn] worker {res['item'][:3]} failed ({tag})", flush=True)
            print(f"[panel] {n}/{len(items)} workers done ({tag})", flush=True)

    # aggregate: per design, per ligand -> mean dG over seeds/shards
    dg = {}      # design_id -> ligand -> [dG...]
    ddg = {}     # design_id -> ligand -> [ddG...]
    for h in done:
        if not os.path.exists(h["oj"]):
            continue
        r = json.load(open(h["oj"])); lig = r["ligand"]
        for did, v in r["designs"].items():
            dg.setdefault(did, {}).setdefault(lig, []).append(v["dG"])
            ddg.setdefault(did, {}).setdefault(lig, []).append(v["ddG_vs_wt"])

    rows = []
    for d in lib:
        did = d["id"]
        if did not in dg or target not in dg[did]:
            continue
        mean_dg = {lig: round(statistics.mean(vs), 3) for lig, vs in dg[did].items()}
        if not all(lig in mean_dg for lig in ligands):
            continue
        best_decoy = min(mean_dg[x] for x in decoys)
        margin = round(mean_dg[target] - best_decoy, 3)   # <0 = target-specific vs best decoy
        row = {"id": did, "n_mut": d["n_mut"], "mutations": d["mutations"],
               "dG": mean_dg, "margin_vs_best_decoy": margin,
               "ddG_vs_wt": {lig: round(statistics.mean(ddg[did][lig]), 3)
                             for lig in ligands if lig in ddg[did]}}
        # optional pairwise margin vs a specific rival (e.g. testosterone vs progesterone)
        if rival and rival in mean_dg:
            row["margin_vs_rival"] = round(mean_dg[target] - mean_dg[rival], 3)
        rows.append(row)
    sort_key = "margin_vs_rival" if rival else "margin_vs_best_decoy"
    rows.sort(key=lambda r: r.get(sort_key, 1e9))   # most negative (specific) first
    out = {"target": target, "rival": rival, "decoys": decoys, "seeds": seeds,
           "sort_key": sort_key, "n_designs_scored": len(rows),
           "ranked": rows, "top": rows[:args.top]}
    json.dump(out, open(args.out_json, "w"), indent=2)

    rlabel = f"{target} vs {rival}" if rival else f"{target} vs best decoy"
    print(f"\n==== TIER-1 SPECIFICITY SCREEN: {len(rows)} designs; top {args.top} by "
          f"{rlabel} margin (dG_{target[:4]} - dG_rival; <0 = specific) ====")
    print(f"{'id':9s} {'margin':>7s} {'estr':>7s} {'test':>7s} {'prog':>7s} {'cort':>7s}  n_mut")
    for r in rows[:args.top]:
        g = r["dG"]
        print(f"{r['id']:9s} {r.get(sort_key,0):7.2f} {g.get('estradiol',0):7.2f} "
              f"{g.get('testosterone',0):7.2f} {g.get('progesterone',0):7.2f} "
              f"{g.get('cortisol',0):7.2f}  {r['n_mut']}")
    print(f"\n[design_score] wrote {args.out_json}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("worker")
    w.add_argument("--ligand", required=True); w.add_argument("--seed", required=True)
    w.add_argument("--designs", required=True); w.add_argument("--panel", default="data/steroid_panel.csv")
    w.add_argument("--boltz_root", default="results/stage1_wt_validation/boltz")
    w.add_argument("--work_dir", required=True); w.add_argument("--out_json", required=True)
    w.set_defaults(func=cmd_worker)
    p = sub.add_parser("panel")
    p.add_argument("--library", required=True); p.add_argument("--panel", default="data/steroid_panel.csv")
    p.add_argument("--boltz_root", default="results/stage1_wt_validation/boltz")
    p.add_argument("--seeds", default="1"); p.add_argument("--jobs", type=int, default=32)
    p.add_argument("--shards", type=int, default=8); p.add_argument("--top", type=int, default=20)
    p.add_argument("--target", default="estradiol", help="design target ligand")
    p.add_argument("--rival", default=None,
                   help="rank by dG(target)-dG(rival), e.g. --target testosterone --rival progesterone")
    p.add_argument("--work_root", required=True); p.add_argument("--out_json", required=True)
    p.set_defaults(func=cmd_panel)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
