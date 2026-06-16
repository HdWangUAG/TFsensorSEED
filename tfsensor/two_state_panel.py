"""Two-state (apo→holo) allosteric-efficacy panel — the agonist/antagonist axis.

Binding affinity (ΔΔG) ≠ fluorescence amplitude. A ligand can BIND yet not ACTIVATE
(antagonist) or bind weakly yet strongly open the dimer (agonist). The fluorescence
amplitude tracks the apo→holo DBD opening, so we measure, per variant, with a MATCHED
mutant apo reference:

    opening(variant, ligand) = mean DBD(holo: variant+ligand) − mean DBD(matched apo: variant)

DBD = mean Cα distance between chains A/B at the HTH anchors 37/40 (closed↔open).
We then ask whether this opening reproduces the experimental fluorescence-amplitude
order (e.g. L147R: cortisol > progesterone > testosterone≈0). If it does, opening joins
ΔΔG as the **two-state filter** for Stage-3 designs (bind AND activate).

Run in the pyrosetta venv (has lcseed for the DBD metric):
    python -m tfsensor.two_state_panel --out_json results/stage3_apo/two_state.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics

from tfsensor.allostery import dbd_distance
from tfsensor.physics_panel import _load_panel

# variant -> (holo_boltz_root, holo_prefix, apo_boltz_root)  [apo job = <variant>_apo]
VARIANTS = {
    "wt":    ("results/stage1_wt_validation/boltz", "wt",    "results/stage3_apo/wt"),
    "l147r": ("results/stage1d_mutants/l147r/boltz", "l147r", "results/stage3_apo/l147r"),
    "f119w": ("results/stage1d_mutants/f119w/boltz", "f119w", "results/stage3_apo/f119w"),
}

# experimental fluorescence amplitude (approx a.u.; 0 = no response). For rank-corr.
EXP_AMPLITUDE = {
    "wt":    {"progesterone": 150000, "testosterone": 150000, "cortisol": 0, "estradiol": 0},
    "l147r": {"cortisol": 25000, "progesterone": 12000, "testosterone": 0, "estradiol": 0},
    "f119w": {"testosterone": 150000, "progesterone": 150000, "cortisol": 40000, "estradiol": 0},
}


def _models(boltz_root, seed, job):
    patt = os.path.join(boltz_root, f"seed{seed}", "boltz_results_inputs",
                        "predictions", job, f"{job}_model_*.pdb")
    return sorted(glob.glob(patt))


def _mean_dbd(boltz_root, job, seeds):
    vals = []
    for s in seeds:
        for m in _models(boltz_root, s, job):
            vals.append(dbd_distance(m))
    if not vals:
        return None, None, 0
    return (round(statistics.mean(vals), 3),
            round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0, len(vals))


def _spearman(xs, ys):
    """Rank correlation (no scipy). Returns None if <3 paired points."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for rank, i in enumerate(order):
            r[i] = rank
        return r
    a, b = ranks([p[0] for p in pairs]), ranks([p[1] for p in pairs])
    n = len(pairs)
    d2 = sum((a[i] - b[i]) ** 2 for i in range(n))
    return round(1 - 6 * d2 / (n * (n * n - 1)), 3)


def run(seeds, panel_csv, out_json):
    target, decoys, _ = _load_panel(panel_csv)
    ligands = [target] + decoys
    out = {"metric": "boltz_holo_minus_matched_apo_DBD_opening_37_40",
           "seeds": seeds, "variants": {}}

    for var, (holo_root, holo_prefix, apo_root) in VARIANTS.items():
        apo_mean, apo_sd, apo_n = _mean_dbd(apo_root, f"{var}_apo", seeds)
        rec = {"apo_dbd": apo_mean, "apo_sd": apo_sd, "apo_n_models": apo_n, "ligands": {}}
        for lig in ligands:
            hm, hsd, hn = _mean_dbd(holo_root, f"{holo_prefix}_{lig}", seeds)
            opening = round(hm - apo_mean, 3) if (hm is not None and apo_mean is not None) else None
            rec["ligands"][lig] = {"holo_dbd": hm, "holo_sd": hsd, "n_models": hn,
                                   "opening": opening}
        out["variants"][var] = rec

    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    json.dump(out, open(out_json, "w"), indent=2)

    # ---- report ----
    print("==== TWO-STATE DBD OPENING (holo − matched apo, Å; higher = more activation) ====")
    for var, rec in out["variants"].items():
        if rec["apo_dbd"] is None:
            print(f"\n{var}: apo not folded yet — skipping")
            continue
        print(f"\n{var}: apo DBD = {rec['apo_dbd']} Å ({rec['apo_n_models']} models)")
        ranked = sorted(((l, rec["ligands"][l]["opening"]) for l in ligands
                         if rec["ligands"][l]["opening"] is not None),
                        key=lambda kv: -kv[1])
        for l, op in ranked:
            exp = EXP_AMPLITUDE.get(var, {}).get(l)
            print(f"   {l:13s} opening = {op:+6.2f} Å   (exp amplitude ~{exp})")
        # rank correlation vs experimental amplitude
        ord_ligs = [l for l, _ in ranked]
        xs = [rec["ligands"][l]["opening"] for l in ord_ligs]
        ys = [EXP_AMPLITUDE.get(var, {}).get(l) for l in ord_ligs]
        rho = _spearman(xs, ys)
        pred_order = " > ".join(ord_ligs)
        print(f"   predicted activation order: {pred_order}")
        print(f"   Spearman(opening, exp amplitude) = {rho}")
        out["variants"][var]["spearman_vs_exp_amplitude"] = rho

    json.dump(out, open(out_json, "w"), indent=2)
    print(f"\n[two_state] wrote {out_json}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", default="1,42,2024")
    ap.add_argument("--panel", default="data/steroid_panel.csv")
    ap.add_argument("--out_json", default="results/stage3_apo/two_state.json")
    args = ap.parse_args()
    seeds = [s.strip() for s in args.seeds.split(",") if s.strip()]
    run(seeds, args.panel, args.out_json)


if __name__ == "__main__":
    main()
