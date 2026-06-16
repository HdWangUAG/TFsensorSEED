"""The "NO-GO method": a coupled bind x switch biosensor-function score.

Stage-1 showed binding alone is the wrong selectivity axis, and the trigger panel
showed that in WT the testosterone-class (4-en-3-one) steroids open the DBD switch
while estradiol stays closed. But the fluorescence readout is proportional to the
TF that is BOTH bound AND in the open (derepressed) state, so the quantity that
actually predicts signal is a *product* of the two axes:

    biosensor_score(ligand) ~ P(bound) * P(open | bound)

We proxy P(bound) with the Boltz affinity_probability_binary (already in [0,1],
a literal binding probability) and P(open|bound) with the seed-averaged DBD
opening (holo - apo at anchors 37/40), clamped at 0 (a ligand that keeps the
dimer closed produces no signal). WT validation: testosterone (the experimental
responder) should score high and estradiol low (the non-responder). The Stage-3
design objective then inverts this for estradiol — maximize estradiol's coupled
score relative to the decoys; this is the metric the redesign is scored against.

    python -m tfsensor.biosensor_score \
        --boltz_go_nogo results/stage1_wt_validation/boltz/go_nogo.json \
        --trigger_go_nogo results/stage1c_trigger/trigger_go_nogo.json \
        --out_json results/stage1c_trigger/biosensor_score.json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics


def _mean_bp_per_ligand(boltz_go_nogo):
    """Seed-average Boltz binder-prob per ligand from the go_nogo JSON.

    Layout: ``scores[seed][ligand] = binder_prob``; target/decoys under ``summary``.
    """
    d = json.load(open(boltz_go_nogo))
    scores = d["scores"]                 # seed -> ligand -> bp
    names = set()
    for s in scores.values():
        names.update(s.keys())
    out = {}
    for name in names:
        vals = [s[name] for s in scores.values() if name in s]
        out[name] = round(statistics.mean(vals), 4)
    return out, d["summary"]["target"], d["summary"]["decoys"]


def run(boltz_go_nogo, trigger_go_nogo, out_json):
    bp, target, decoys = _mean_bp_per_ligand(boltz_go_nogo)
    trig = json.load(open(trigger_go_nogo))
    opening = trig["mean_opening_per_ligand"]
    names = [target] + decoys

    rows = {}
    for name in names:
        p_bound = bp.get(name)
        open_a = opening.get(name)
        if p_bound is None or open_a is None:
            continue
        coupled = round(p_bound * max(open_a, 0.0), 4)
        rows[name] = {"p_bound_boltz": p_bound,
                      "dbd_opening_A": open_a,
                      "biosensor_score": coupled}

    tgt = rows.get(target, {}).get("biosensor_score")
    decoy_scores = {d: rows[d]["biosensor_score"] for d in decoys if d in rows}
    best_decoy = max(decoy_scores.values()) if decoy_scores else None
    margin = round(tgt - best_decoy, 4) if (tgt is not None and best_decoy is not None) else None
    target_is_best = bool(decoy_scores) and tgt is not None and tgt > best_decoy

    out = {
        "metric": "coupled_biosensor_score = P(bound)_boltz * max(DBD_opening,0)",
        "target": target,
        "decoys": decoys,
        "per_ligand": rows,
        "target_biosensor_score": tgt,
        "best_decoy_biosensor_score": best_decoy,
        "margin_vs_best_decoy": margin,
        "GO": target_is_best,
    }
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    json.dump(out, open(out_json, "w"), indent=2)

    print(f"{'ligand':14s} {'P(bound)':>9s} {'open(A)':>8s} {'biosensor':>10s}")
    for name in names:
        if name in rows:
            r = rows[name]
            tag = "  <- TARGET" if name == target else ""
            print(f"{name:14s} {r['p_bound_boltz']:9.3f} "
                  f"{r['dbd_opening_A']:8.2f} {r['biosensor_score']:10.3f}{tag}")
    verdict = "GO" if out["GO"] else "NO-GO"
    print(f"\n[biosensor] GO/NO-GO = {verdict}  "
          f"({target} coupled score {tgt} vs best decoy {best_decoy}; "
          f"margin {margin})")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--boltz_go_nogo", required=True)
    ap.add_argument("--trigger_go_nogo", required=True)
    ap.add_argument("--out_json", required=True)
    args = ap.parse_args()
    run(args.boltz_go_nogo, args.trigger_go_nogo, args.out_json)


if __name__ == "__main__":
    main()
