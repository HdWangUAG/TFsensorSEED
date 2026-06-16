"""Seed-replicated selectivity aggregation + WT GO/NO-GO test.

Adapted from AcylSEED ``fatb/replicate_summary.py``. The robust quantity (the
FatB1 lesson) is the seed-consistent RELATIVE ordering / margin, not a single
structure's argmax. For AcrR WT validation the experimental control is:

    WT AcrR prefers estradiol over testosterone AND progesterone.

So GO requires estradiol to outrank both of those decoys in a majority of seeds.
The specificity MARGIN (design objective) is bp(estradiol) - max(bp(decoys)).

This module is model-agnostic: a "scores" mapping is ``{seed: {steroid: value}}``
with ``higher_is_better`` (Boltz binder-prob & Protenix confidence = True;
physics dG = False). For Boltz it can build that mapping directly from per-seed
prediction dirs via ``tfsensor.boltz_selectivity``.

CLI (Boltz):
    python -m tfsensor.replicate_summary boltz \
        --seed_dir 1:results/stage1_wt_validation/boltz/seed1 \
        --seed_dir 42:results/stage1_wt_validation/boltz/seed42 \
        --seed_dir 2024:results/stage1_wt_validation/boltz/seed2024 \
        --pocket data/pocket_residues.json --panel data/steroid_panel.csv \
        --target estradiol --controls testosterone,progesterone \
        --out_json results/stage1_wt_validation/boltz/go_nogo.json
"""
from __future__ import annotations

import argparse
import json
import statistics as stats


def summarize(scores, target, controls, decoys, higher_is_better=True):
    """scores: {seed: {steroid: value}}. Returns a GO/NO-GO summary dict."""
    seeds = sorted(scores)
    sign = 1.0 if higher_is_better else -1.0

    per_seed = {}
    target_beats_all_controls = 0
    target_is_top = 0
    margins = []
    for s in seeds:
        sc = scores[s]
        if target not in sc:
            continue
        # control test: target preferred over EACH named control
        beats = {c: (sign * (sc[target] - sc[c]) > 0) for c in controls if c in sc}
        all_controls = all(beats.values()) and len(beats) == len(controls)
        target_beats_all_controls += int(all_controls)
        # is target the overall best across all steroids present?
        best = (max(sc, key=sc.get) if higher_is_better else min(sc, key=sc.get))
        target_is_top += int(best == target)
        # specificity margin vs best decoy
        dvals = [sc[d] for d in decoys if d in sc]
        if dvals:
            best_decoy = (max(dvals) if higher_is_better else min(dvals))
            margin = sign * (sc[target] - best_decoy)
            margins.append(margin)
        per_seed[s] = {"scores": sc, "beats_all_controls": all_controls,
                       "target_is_top": best == target,
                       "margin_vs_best_decoy": margins[-1] if dvals else None}

    n = len([s for s in seeds if target in scores[s]])
    summary = {
        "target": target, "controls": controls, "decoys": decoys,
        "higher_is_better": higher_is_better, "n_seeds": n,
        "seeds_target_beats_all_controls": target_beats_all_controls,
        "seeds_target_is_top": target_is_top,
        "margin_mean": (round(stats.mean(margins), 4) if margins else None),
        "margin_min": (round(min(margins), 4) if margins else None),
        "margin_all_positive": (all(m > 0 for m in margins) if margins else None),
        "per_seed": per_seed,
    }
    # GO if target beats both controls in a strict majority of seeds.
    summary["GO"] = n > 0 and target_beats_all_controls >= (n // 2 + 1)
    return summary


def boltz_scores_from_dirs(seed_dirs, pocket_json, panel_csv):
    """{seed: {steroid: binder_prob}} from per-seed Boltz prediction dirs."""
    from tfsensor.boltz_selectivity import (collect, load_pocket,
                                            load_panel_names, _name_key)
    pocket = load_pocket(pocket_json)
    names = load_panel_names(panel_csv)
    out = {}
    for seed, d in seed_dirs.items():
        recs = collect([d], pocket)
        out[seed] = {}
        for r in recs:
            k = _name_key(r["name"], names)
            if r["affinity_probability_binary"] is not None:
                out[seed][k] = r["affinity_probability_binary"]
    return out


def protenix_scores(out_dir, panel_csv, seeds, prefix="wt", metric="ligand_iptm"):
    """{seed: {steroid: metric}} from a Protenix panel output dir.

    metric: 'ligand_iptm' or 'ligand_plddt' (higher = more confident binding).
    """
    from tfsensor.protenix_runner import analyze_job
    from tfsensor.boltz_selectivity import load_panel_names
    names = load_panel_names(panel_csv)
    out = {}
    for seed in seeds:
        out[seed] = {}
        for n in names:
            rec = analyze_job(out_dir, f"{prefix}_{n}", seed=seed)
            if rec and rec["best"] and rec["best"].get(metric) is not None:
                out[seed][n] = rec["best"][metric]
    return out


def _parse_seed_dirs(specs):
    out = {}
    for s in specs:
        seed, _, path = s.partition(":")
        out[seed] = path
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("boltz")
    b.add_argument("--seed_dir", action="append", required=True,
                   help="SEED:DIR (repeatable)")
    b.add_argument("--pocket", required=True)
    b.add_argument("--panel", required=True)
    b.add_argument("--target", default="testosterone")
    b.add_argument("--controls", default="progesterone,cortisol")
    b.add_argument("--decoys", default="progesterone,cortisol,estradiol")
    b.add_argument("--out_json", required=True)
    p = sub.add_parser("protenix")
    p.add_argument("--out_dir", required=True, help="Protenix panel output dir")
    p.add_argument("--panel", required=True)
    p.add_argument("--seeds", default="1,42,2024")
    p.add_argument("--prefix", default="wt")
    p.add_argument("--metric", default="ligand_iptm",
                   choices=["ligand_iptm", "ligand_plddt"])
    p.add_argument("--target", default="testosterone")
    p.add_argument("--controls", default="progesterone,cortisol")
    p.add_argument("--decoys", default="progesterone,cortisol,estradiol")
    p.add_argument("--out_json", required=True)
    p.set_defaults(which="protenix")

    b.set_defaults(which="boltz")
    args = ap.parse_args()

    if getattr(args, "which", "boltz") == "protenix":
        scores = protenix_scores(args.out_dir, args.panel,
                                 args.seeds.split(","), args.prefix, args.metric)
        model = f"protenix:{args.metric}"
    else:
        seed_dirs = _parse_seed_dirs(args.seed_dir)
        scores = boltz_scores_from_dirs(seed_dirs, args.pocket, args.panel)
        model = "boltz"
    summary = summarize(scores, args.target,
                        args.controls.split(","), args.decoys.split(","),
                        higher_is_better=True)
    json.dump({"model": model, "scores": scores, "summary": summary},
              open(args.out_json, "w"), indent=2)
    print(json.dumps(summary, indent=2))
    print(f"\n[{model}] GO/NO-GO = {'GO' if summary['GO'] else 'NO-GO'}  "
          f"(testosterone beats both controls in "
          f"{summary['seeds_target_beats_all_controls']}/{summary['n_seeds']} seeds; "
          f"margin mean {summary['margin_mean']})")


if __name__ == "__main__":
    main()
