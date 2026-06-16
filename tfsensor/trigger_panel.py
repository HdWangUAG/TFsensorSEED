"""Stage-1c allosteric-trigger panel: the function-coupled selectivity metric.

The biosensor readout is FLUORESCENCE (GFP), i.e. *derepression*: the ligand
must not only bind, it must drive the apo->holo conformational switch that
detaches the AcrR dimer from DNA. So raw binding energy is the wrong selectivity
axis. The right axis is how much each ligand *opens the DBD switch* — the mean
Calpha distance between chains A and B at the HTH/DBD anchor residues 37 and 40
(small = DNA-bound/closed, large = released/open). A ligand that binds tightly
but fails to open the switch gives no signal (a competitive antagonist); the
responder should open it hardest.

WT validation ground truth: WT AcrR responds to TESTOSTERONE (and other
4-en-3-one steroids), NOT estradiol. So for WT we expect the testosterone-class
steroids to open the switch and estradiol to stay closed (dark). Estradiol is the
eventual ENGINEERING target (Stage 3+): redesign so estradiol opens the switch.

For each steroid x seed we average the DBD distance over ALL Boltz diffusion
samples (conformational heterogeneity), reference it to the apo state, and rank
ligands by opening; the target (from the panel CSV) should open it most.

Run in any env with the lcseed import path (pyrosetta venv works):
    python -m tfsensor.trigger_panel \
        --panel data/steroid_panel.csv \
        --boltz_root results/stage1_wt_validation/boltz \
        --apo data/AcrR_protein_only.pdb \
        --seeds 1,42,2024 \
        --out_json results/stage1c_trigger/trigger_go_nogo.json
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import statistics

from tfsensor.allostery import dbd_distance


def _load_panel(panel_csv):
    target, decoys = None, []
    with open(panel_csv) as fh:
        for row in csv.DictReader(fh):
            if row["role"] == "target":
                target = row["name"]
            else:
                decoys.append(row["name"])
    return target, decoys


def _holo_models(boltz_root, seed, name, prefix="wt"):
    job = f"{prefix}_{name}"
    patt = os.path.join(
        boltz_root, f"seed{seed}", "boltz_results_inputs", "predictions",
        job, f"{job}_model_*.pdb")
    return sorted(glob.glob(patt))


def run_panel(panel_csv, boltz_root, apo_pdb, seeds, out_json, prefix="wt"):
    target, decoys = _load_panel(panel_csv)
    names = [target] + decoys
    apo_dbd = round(dbd_distance(apo_pdb), 3)
    print(f"apo DBD(37/40) = {apo_dbd} A (reference)\n")

    per_seed = {}          # seed -> name -> {dbd_mean, dbd_std, n_models, opening}
    for seed in seeds:
        per_seed[seed] = {}
        for name in names:
            models = _holo_models(boltz_root, seed, name, prefix)
            if not models:
                print(f"[warn] no holo models: seed {seed} {name}")
                continue
            dists = [dbd_distance(m) for m in models]
            mean_d = statistics.mean(dists)
            per_seed[seed][name] = {
                "dbd_mean": round(mean_d, 3),
                "dbd_std": round(statistics.pstdev(dists), 3) if len(dists) > 1 else 0.0,
                "n_models": len(dists),
                "opening": round(mean_d - apo_dbd, 3),   # holo - apo (>0 = derepressing)
            }
            print(f"[seed {seed}] {name:13s} DBD {mean_d:6.2f} "
                  f"(+/-{per_seed[seed][name]['dbd_std']:.2f}, n={len(dists)})  "
                  f"opening {per_seed[seed][name]['opening']:+.2f}")

    # seed-averaged opening per ligand
    mean_open = {}
    for name in names:
        vals = [per_seed[s][name]["opening"] for s in seeds if name in per_seed[s]]
        if vals:
            mean_open[name] = round(statistics.mean(vals), 3)

    # per-seed: does estradiol open MORE than every decoy?
    seed_target_wins, margins = 0, []
    for s in seeds:
        sc = per_seed[s]
        if target not in sc:
            continue
        decoy_open = [sc[d]["opening"] for d in decoys if d in sc]
        if not decoy_open:
            continue
        margin = round(sc[target]["opening"] - max(decoy_open), 3)  # >0 = target opens most
        margins.append(margin)
        seed_target_wins += int(all(
            sc[target]["opening"] > sc[d]["opening"] for d in decoys if d in sc))

    n = len([s for s in seeds if target in per_seed[s]])
    out = {
        "metric": "boltz_holo_minus_apo_DBD_opening_37_40",
        "rationale": "fluorescence reports derepression: rank by allosteric opening, not binding",
        "higher_is_better": True,
        "apo_dbd": apo_dbd,
        "target": target,
        "decoys": decoys,
        "n_seeds": n,
        "seeds_target_opens_most": seed_target_wins,
        "margin_mean": round(statistics.mean(margins), 4) if margins else None,
        "margin_min": round(min(margins), 4) if margins else None,
        "margin_all_positive": bool(margins) and all(m > 0 for m in margins),
        "mean_opening_per_ligand": mean_open,
        "per_seed": per_seed,
        "GO": bool(margins) and seed_target_wins == n and n > 0,
    }
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    json.dump(out, open(out_json, "w"), indent=2)
    print("\n" + json.dumps({k: out[k] for k in
          ["metric", "apo_dbd", "mean_opening_per_ligand",
           "seeds_target_opens_most", "margin_mean", "GO"]}, indent=2))
    verdict = "GO" if out["GO"] else "NO-GO"
    print(f"\n[trigger] GO/NO-GO = {verdict}  "
          f"(testosterone opens the switch most in {seed_target_wins}/{n} seeds; "
          f"margin mean {out['margin_mean']})")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panel", required=True)
    ap.add_argument("--boltz_root", required=True)
    ap.add_argument("--apo", required=True)
    ap.add_argument("--seeds", default="1,42,2024")
    ap.add_argument("--out_json", required=True)
    ap.add_argument("--prefix", default="wt",
                    help="Boltz job prefix (wt / f119w / l147r) -> finds <prefix>_<ligand>")
    args = ap.parse_args()
    seeds = [s.strip() for s in args.seeds.split(",") if s.strip()]
    run_panel(args.panel, args.boltz_root, args.apo, seeds, args.out_json, args.prefix)


if __name__ == "__main__":
    main()
