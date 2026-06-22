"""#4 retrodiction benchmark on ORIENTATION-CORRECTED poses (panel must-fix #4).

Decides whether ANY in-silico pre-filter survives, and tests the Moderator's
guardrail that selectivity *might* be learnable once poses are A-ring-correct. We
do NOT use the Boltz 35.5/38 A gate here (it is a Boltz-self-derived heuristic,
resolved 2026-06-22) -- the discriminator is flex-ddG dG_separated (Tier-1).

Method:
  1. For each steroid x seed, pick the lowest-index Boltz WT-holo model whose
     A-ring 3-keto is SAR-consistent (nearer E106/R123 than Q88) -- the panel's
     orientation filter (tfsensor.rescore_oriented._orientation_ok). One pose per
     seed -> seed spread; report the orientation-consistent availability.
  2. flex-ddG score WT + the known singles (I61L, L85I, E106L) on each oriented
     pose (tfsensor.design_score worker, --holo_pdb override). dG per
     (variant, steroid) -> median + spread over seeds.
  3. Score retrodiction against the empirical GFP scan:
       - WT steroid ORDER: dG should rank testosterone < cortisol < progesterone
         (tighter = more negative) and estradiol weakest (fold 135>104>60>>0.8).
       - testosterone-selectivity SHIFT for each single: bias = (dG_test - dG_prog)_mut
         - (dG_test - dG_prog)_WT must be < 0 (more test-over-prog selective),
         matching the scan (I61L/L85I/E106L raise the test/prog fold ratio).
  PASS only if WT order is recovered AND >=2/3 bias signs are correct, with the
  seed spread reported. A66M (basal leak) is EXCLUDED -- leak is an apo/basal
  phenomenon, not a binding-dG observable, and is unmeasured in the 4-steroid scan.

Run (PyRosetta env):
    PYTHONPATH=. ~/.conda/envs/pyrosetta/bin/python -m tfsensor.ml.bo.retrodict \
        --jobs 12 --out_json results/stage4_bo/retrodiction.json
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

from tfsensor import config
from tfsensor.ml.bo import seed as bo_seed
from tfsensor.rescore_oriented import _orientation_ok

BOLTZ_ROOT = os.path.join(config.REPO_ROOT, "results/stage1_wt_validation/boltz")
PANEL = os.path.join(config.REPO_ROOT, "data/steroid_panel.csv")
STEROIDS = ["testosterone", "progesterone", "cortisol", "estradiol"]
SEEDS = ["1", "42", "2024"]
# known singles to retrodict (testosterone-selectivity shifts); WT is the baseline
KNOWN_SINGLES = ["I61L", "L85I", "E106L"]


def _models(boltz_root, lig, s):
    job = f"wt_{lig}"
    return sorted(glob.glob(os.path.join(
        boltz_root, f"seed{s}", "boltz_results_inputs", "predictions", job,
        f"{job}_model_*.pdb")))


def select_oriented(boltz_root=BOLTZ_ROOT, steroids=STEROIDS, seeds=SEEDS):
    """{steroid: [(seed, pose_pdb), ...]} -- the lowest-index SAR-consistent model
    per seed (highest Boltz confidence among the orientation-correct poses)."""
    chosen, avail = {}, {}
    for lig in steroids:
        picks, n_ok, n_tot = [], 0, 0
        for s in seeds:
            ms = _models(boltz_root, lig, s)
            n_tot += len(ms)
            cons = [m for m in ms if _orientation_ok(m)]
            n_ok += len(cons)
            if cons:
                picks.append((s, cons[0]))      # model_* sorted -> lowest index first
        chosen[lig] = picks
        avail[lig] = {"consistent": n_ok, "total": n_tot, "seeds_used": len(picks)}
    return chosen, avail


def _empirical():
    """Empirical GFP fold per (variant, steroid) from the round-0 scan."""
    rows, _ = bo_seed.load_scan()
    return {v: rows.get(v, {}) for v in ["WT"] + KNOWN_SINGLES}


def _library(work_root):
    lib = [{"id": m, "n_mut": 1, "mutations": [m]} for m in KNOWN_SINGLES]
    path = os.path.join(work_root, "known_library.json")
    json.dump(lib, open(path, "w"))
    return path


def _run_worker(lig, s, pose, lib_path, work_root):
    wd = os.path.join(work_root, f"{lig}_s{s}")
    os.makedirs(wd, exist_ok=True)
    oj = os.path.join(wd, "out.json")
    cmd = [sys.executable, "-m", "tfsensor.design_score", "worker",
           "--ligand", lig, "--seed", s, "--designs", lib_path, "--panel", PANEL,
           "--work_dir", wd, "--out_json", oj, "--holo_pdb", pose]
    with open(os.path.join(wd, "log"), "w") as log:
        rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
    return {"lig": lig, "seed": s, "oj": oj, "rc": rc}


def _spread(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return {"median": round(statistics.median(xs), 3), "n": len(xs),
            "min": round(min(xs), 3), "max": round(max(xs), 3),
            "range": round(max(xs) - min(xs), 3)}


def score(dg_wt, dg_design, avail, emp):
    """Build the retrodiction verdict from aggregated dG (median over seeds)."""
    wt_med = {lig: (_spread(dg_wt.get(lig, []) ) or {}).get("median") for lig in STEROIDS}
    # --- WT order: tighter (more negative) dG should track higher empirical fold ---
    binders = ["testosterone", "cortisol", "progesterone"]
    have = [l for l in binders if wt_med.get(l) is not None]
    order_pred = sorted(have, key=lambda l: wt_med[l])              # ascending dG = tightest first
    order_emp = sorted(have, key=lambda l: -emp["WT"].get(l, float("-inf")))  # highest fold first
    est = wt_med.get("estradiol")
    est_weakest = (est is not None and all(wt_med[l] < est for l in have))
    wt_order_ok = (order_pred == order_emp) and (est_weakest or est is None)

    # --- testosterone-selectivity shift per single ---
    bias = {}
    wt_gap = (wt_med.get("testosterone"), wt_med.get("progesterone"))
    for m in KNOWN_SINGLES:
        t = (_spread(dg_design.get(m, {}).get("testosterone", [])) or {}).get("median")
        p = (_spread(dg_design.get(m, {}).get("progesterone", [])) or {}).get("median")
        if None in (t, p) or None in wt_gap:
            bias[m] = {"shift": None, "sign_ok": None,
                       "note": "missing oriented dG (likely flipped-pose starvation)"}
            continue
        shift = (t - p) - (wt_gap[0] - wt_gap[1])   # <0 => more test-over-prog selective
        emp_ratio_mut = emp[m].get("testosterone", float("nan")) / max(
            emp[m].get("progesterone", float("nan")), 1e-9)
        emp_ratio_wt = emp["WT"].get("testosterone", float("nan")) / max(
            emp["WT"].get("progesterone", float("nan")), 1e-9)
        bias[m] = {"shift": round(shift, 3), "sign_ok": shift < 0,
                   "emp_test_over_prog_mut": round(emp_ratio_mut, 2),
                   "emp_test_over_prog_wt": round(emp_ratio_wt, 2)}
    signs = [b["sign_ok"] for b in bias.values() if b["sign_ok"] is not None]
    bias_ok = len(signs) >= 2 and sum(signs) >= 2
    verdict = bool(wt_order_ok and bias_ok)
    return {"wt_dG_median": wt_med, "wt_order_pred": order_pred, "wt_order_emp": order_emp,
            "estradiol_weakest": est_weakest, "wt_order_ok": wt_order_ok,
            "bias": bias, "bias_ok": bias_ok, "n_bias_evaluable": len(signs),
            "PASS": verdict,
            "orientation_availability": avail}


def run(out_json, jobs=12, work_root=None):
    work_root = os.path.abspath(work_root or os.path.join(config.BO_DIR, "retrodict_work")) \
        if hasattr(config, "BO_DIR") else os.path.abspath(
            work_root or os.path.join(config.REPO_ROOT, "results/stage4_bo/retrodict_work"))
    os.makedirs(work_root, exist_ok=True)
    chosen, avail = select_oriented()
    emp = _empirical()
    lib_path = _library(work_root)

    print("=== orientation-consistent pose availability (A-ring 3-keto nearer E106/R123 than Q88) ===")
    for lig in STEROIDS:
        a = avail[lig]
        print(f"  {lig:13s} {a['consistent']:2d}/{a['total']:2d} consistent; "
              f"{a['seeds_used']} seed(s) scorable")

    items = [(lig, s, pose) for lig, picks in chosen.items() for (s, pose) in picks]
    if not items:
        print("[retrodict] NO orientation-consistent poses -> cannot score. Re-fold WT holo.")
        return None
    print(f"\n[retrodict] launching {len(items)} flex-ddG workers (jobs={jobs}) ...", flush=True)
    done = []
    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = [ex.submit(_run_worker, lig, s, pose, lib_path, work_root)
                for (lig, s, pose) in items]
        for n, fut in enumerate(cf.as_completed(futs), 1):
            r = fut.result(); done.append(r)
            print(f"[retrodict] {n}/{len(items)} {r['lig']} s{r['seed']} "
                  f"{'ok' if r['rc'] == 0 else 'rc=' + str(r['rc'])}", flush=True)

    # aggregate: dg_wt[lig] = [over seeds]; dg_design[id][lig] = [over seeds]
    dg_wt, dg_design = {}, {m: {} for m in KNOWN_SINGLES}
    for r in done:
        if r["rc"] != 0 or not os.path.exists(r["oj"]):
            continue
        o = json.load(open(r["oj"])); lig = o["ligand"]
        dg_wt.setdefault(lig, []).append(o["dG_wt"])
        for did, v in o["designs"].items():
            dg_design[did].setdefault(lig, []).append(v["dG"])

    result = score(dg_wt, dg_design, avail, emp)
    result["raw_dg_wt"] = {l: _spread(v) for l, v in dg_wt.items()}
    result["raw_dg_design"] = {m: {l: _spread(v) for l, v in by.items()}
                               for m, by in dg_design.items()}
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    json.dump(result, open(out_json, "w"), indent=2)
    _report(result, out_json)
    return result


def _report(r, out_json):
    print("\n==== #4 RETRODICTION ON ORIENTATION-CORRECTED POSES ====")
    print(f"WT dG medians: " + "  ".join(
        f"{l[:4]}={ (r['wt_dG_median'].get(l) if r['wt_dG_median'].get(l) is not None else float('nan')):.2f}"
        for l in STEROIDS))
    print(f"WT order  pred={r['wt_order_pred']}  emp={r['wt_order_emp']}  "
          f"estradiol_weakest={r['estradiol_weakest']}  -> {'OK' if r['wt_order_ok'] else 'FAIL'}")
    for m, b in r["bias"].items():
        print(f"  bias {m:6s} shift={b['shift']}  sign_ok={b['sign_ok']}  ({b.get('note','')})")
    print(f"bias_ok={r['bias_ok']} ({r['n_bias_evaluable']}/3 evaluable)")
    print(f"\n>>> RETRODICTION {'PASS' if r['PASS'] else 'FAIL'} <<<")
    print(f"[retrodict] wrote {out_json}")
    md = out_json.rsplit(".", 1)[0] + ".md"
    lines = ["# #4 retrodiction on orientation-corrected poses",
             "",
             "Discriminator = flex-ddG dG_separated (NOT the Boltz Å gate — a self-derived "
             "heuristic). Orientation filter = A-ring 3-keto nearer E106/R123 than Q88.", "",
             "## Orientation-consistent pose availability",
             "| steroid | consistent/total | seeds scorable |", "|---|---|---|"]
    for l in STEROIDS:
        a = r["orientation_availability"][l]
        lines.append(f"| {l} | {a['consistent']}/{a['total']} | {a['seeds_used']} |")
    lines += ["", "## WT steroid order (binding dG should track empirical fold)",
              f"- predicted (by dG, tightest first): `{r['wt_order_pred']}`",
              f"- empirical (by GFP fold): `{r['wt_order_emp']}`",
              f"- estradiol weakest: {r['estradiol_weakest']} · **WT order "
              f"{'recovered' if r['wt_order_ok'] else 'NOT recovered'}**", "",
              "## Testosterone-selectivity shift per single "
              "(`(dG_test−dG_prog)_mut − (…)_WT`; <0 = more test-selective)",
              "| single | shift | sign ok | emp test/prog (mut vs WT) | note |",
              "|---|---|---|---|---|"]
    for m, b in r["bias"].items():
        lines.append(f"| {m} | {b['shift']} | {b['sign_ok']} | "
                     f"{b.get('emp_test_over_prog_mut','—')} vs {b.get('emp_test_over_prog_wt','—')} | "
                     f"{b.get('note','')} |")
    lines += ["", f"## Verdict: **{'PASS' if r['PASS'] else 'FAIL'}** "
              f"(WT order {'ok' if r['wt_order_ok'] else 'fail'}; "
              f"bias {'ok' if r['bias_ok'] else 'fail'}, "
              f"{r['n_bias_evaluable']}/3 evaluable).",
              "",
              "_If FAIL or data-starved (target poses mostly A-ring-flipped), no in-silico "
              "pre-filter is justified for testosterone selectivity; rely on the round-1 "
              "wet-lab diagnostic._"]
    open(md, "w").write("\n".join(lines))
    print(f"[retrodict] wrote {md}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--out_json",
                    default=os.path.join(config.REPO_ROOT, "results/stage4_bo/retrodiction.json"))
    ap.add_argument("--work_root", default=None)
    args = ap.parse_args()
    run(args.out_json, jobs=args.jobs, work_root=args.work_root)


if __name__ == "__main__":
    main()
