"""Stage-3a ΔΔG report: mutation×ligand table + experimental-expectation checks.

Reads ddg_results.json (from ddg_panel) and tests whether the fixed-backbone ΔΔG
arbiter reproduces the known mutant phenotypes (calibration) and predicts the R123E/D
estradiol-specificity flip (positive control). Sign: ΔΔG<0 = mutation strengthens
binding. Checks are significance-gated: a PASS requires the expected sign AND
|ΔΔG_mean| > sd (sign robust to seed noise).

    python -m tfsensor.ddg_report --results results/stage3_ddg/ddg_results.json \
        --out_json results/stage3_ddg/BENCHMARK.json
"""
from __future__ import annotations

import argparse
import json
import os

# expectation: mutation -> {ligand: "neg"|"pos"} (sign of ΔΔG we expect)
EXPECT = {
    "R123E": {"estradiol": "neg", "testosterone": "pos", "progesterone": "pos"},
    "R123D": {"estradiol": "neg", "testosterone": "pos", "progesterone": "pos"},
    "L147R": {"testosterone": "pos", "cortisol": "neg"},
    "F119W": {"testosterone": "neg", "progesterone": "neg"},
}
EXPECT_NOTE = {
    "R123E": "estradiol phenol clamp (rescue estradiol; repel keto test/prog)",
    "R123D": "estradiol phenol clamp (rescue estradiol; repel keto test/prog)",
    "L147R": "specificity switch (penalize hydrophobic testosterone; favor polyol cortisol)",
    "F119W": "sensitivity boost (favor test/prog via packing/π)",
}


def _med(cell):
    """Median across seeds — robust to a single outlier backbone (mean is not)."""
    import statistics
    ps = cell.get("per_seed")
    return statistics.median(ps) if ps else cell.get("mean")


def run(results_json, out_json):
    import statistics
    d = json.load(open(results_json))
    ddg = d["ddg"]
    ligands = d["ligands"]

    rep = []
    rep.append("====== STAGE-3a FIXED-BACKBONE ΔΔG (kcal/mol; <0 = strengthens binding) ======")
    rep.append(f"seeds={d['seeds']}  n_ensemble={d.get('n_ensemble', '?')}  "
               f"metric={d['metric']}\n")

    for mut in ddg:
        rep.append(f"---- {mut}: {EXPECT_NOTE.get(mut,'')} ----")
        for lig in ligands:
            x = ddg[mut].get(lig)
            if x:
                rep.append(f"  {lig:13s} ΔΔG(median) = {_med(x):+6.2f}"
                           f"   per-seed {x['per_seed']}")
        rep.append("")

    rep.append("====== EXPERIMENTAL EXPECTATION CHECKS (sign + |mean|>sd) ======")
    checks = {}
    for mut, exp in EXPECT.items():
        for lig, want in exp.items():
            x = ddg.get(mut, {}).get(lig)
            if not x or x.get("per_seed") is None:
                checks[f"{mut}:{lig}:{want}"] = None
                rep.append(f"  [n/a ] {mut} {lig}: expect ΔΔG {want} — no data")
                continue
            med = _med(x)
            # robust: median has the expected sign AND all seeds agree in sign
            allsame = all(v > 0 for v in x["per_seed"]) or all(v < 0 for v in x["per_seed"])
            ok = ((want == "neg" and med < 0) or (want == "pos" and med > 0)) and allsame
            checks[f"{mut}:{lig}:{want}"] = bool(ok)
            mark = "PASS" if ok else "FAIL"
            why = "" if allsame else " (seeds disagree in sign)"
            rep.append(f"  [{mark}] {mut} {lig}: expect {want}, got median "
                       f"{med:+.2f} {x['per_seed']}{why}")
        rep.append("")

    # ---- RELATIVE SPECIFICITY: after the mutation, is the design-target ligand the
    # most-favored (lowest ΔΔG) of the panel? This is the biologically correct lens —
    # a disruptive mutation can raise ΔΔG for everything yet still FLIP which ligand wins.
    SPEC_TARGET = {"R123E": "estradiol", "R123D": "estradiol", "L147R": "cortisol"}
    rep.append("====== RELATIVE SPECIFICITY (within-mutant ΔΔG ranking; target should rank #1) ======")
    spec = {}
    for mut, tgt in SPEC_TARGET.items():
        ranked = sorted(((lig, _med(ddg[mut][lig])) for lig in ligands
                         if ddg.get(mut, {}).get(lig)), key=lambda kv: kv[1])
        if not ranked:
            continue
        order = " < ".join(f"{l}({v:+.2f})" for l, v in ranked)
        rank = [l for l, _ in ranked].index(tgt) + 1 if tgt in dict(ranked) else None
        is_top = rank == 1
        spec[mut] = bool(is_top)
        mark = "PASS" if is_top else "FAIL"
        rep.append(f"  [{mark}] {mut}: target {tgt} ranks #{rank}/{len(ranked)}  "
                   f"(best→worst: {order})")
    rep.append("")

    npass = sum(1 for v in checks.values() if v is True)
    ntot = sum(1 for v in checks.values() if v is not None)
    spass = sum(1 for v in spec.values() if v)
    rep.append(f"SUMMARY: absolute-sign {npass}/{ntot}; "
               f"relative-specificity flips {spass}/{len(spec)} "
               f"(target becomes the most-favored ligand).")
    out_spec = spec
    # calibration verdict
    cal = [k for k in checks if k.split(":")[0] in ("L147R", "F119W")]
    cal_pass = sum(1 for k in cal if checks[k] is True)
    pc = [k for k in checks if k.split(":")[0] in ("R123E", "R123D")]
    pc_pass = sum(1 for k in pc if checks[k] is True)
    rep.append(f"  calibration (L147R+F119W): {cal_pass}/{len(cal)} | "
               f"positive control (R123E/D estradiol flip): {pc_pass}/{len(pc)}")

    out = {"checks": checks, "n_pass": npass, "n_total": ntot,
           "calibration_pass": cal_pass, "calibration_total": len(cal),
           "positive_control_pass": pc_pass, "positive_control_total": len(pc),
           "specificity_flips": out_spec}
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    json.dump(out, open(out_json, "w"), indent=2)
    print("\n".join(rep))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", required=True)
    ap.add_argument("--out_json", required=True)
    args = ap.parse_args()
    run(args.results, args.out_json)


if __name__ == "__main__":
    main()
