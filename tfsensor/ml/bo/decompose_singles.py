"""Decompose the test/progesterone SELECTIVITY of the validated singles.

The minicrew debate (2026-06-23) flagged a decisive, cheap question before any
multi-mutant build: do the validated testosterone-selective singles (I61L, L85I,
E106L) raise the test/prog FOLD RATIO by *gaining* testosterone signal, or by
*losing* progesterone signal (denominator collapse toward baseline)? If it's the
latter, the "three levers" are one axis (global pocket dampening) and stacking
risks a dim/dead sensor — the feared k=2 saturation.

Selectivity S = log10(test) - log10(prog). The shift vs WT decomposes additively:
    ΔS = Δlog(test) - Δlog(prog)
We attribute the selectivity gain to a TESTOSTERONE term (Δlog test) and a
PROGESTERONE term (-Δlog prog), and classify the driver. Uses the existing
single-dose round-0 scan (no new data). Pure numpy.

    PYTHONPATH=. ~/.conda/envs/TF_agent_env/bin/python -m tfsensor.ml.bo.decompose_singles
"""
from __future__ import annotations

import math
import os

from tfsensor import config
from tfsensor.ml.bo import seed

OUT = os.path.join(config.REPO_ROOT, "results/stage4_bo/singles_decomposition.md")
SINGLES = ["I61L", "L85I", "E106L", "I61M", "Q88L", "E106Q"]   # validated + neighbours
EPS = 1.0   # folds <=1 = no induction (same floor as seed.objective_table)


def _f(folds, lig):
    v = folds.get(lig, float("nan"))
    return v if v == v else float("nan")


def decompose():
    rows, _ = seed.load_scan()
    wt = rows["WT"]
    wt_t, wt_p = max(_f(wt, "testosterone"), EPS), max(_f(wt, "progesterone"), EPS)
    s_wt = math.log10(wt_t / wt_p)
    out = []
    for v in SINGLES:
        if v not in rows:
            continue
        f = rows[v]
        t, p = max(_f(f, "testosterone"), EPS), max(_f(f, "progesterone"), EPS)
        c = _f(f, "cortisol")
        dlog_t = math.log10(t) - math.log10(wt_t)        # testosterone signal change
        dlog_p = math.log10(p) - math.log10(wt_p)        # progesterone signal change
        dS = dlog_t - dlog_p                              # selectivity shift vs WT
        # classify the driver of any selectivity GAIN
        if dS <= 0.05:
            driver = "no selectivity gain"
        elif dlog_t >= -0.1:        # testosterone roughly held or gained
            driver = "GOOD: prog-loss WITH test retained"
        elif dlog_t < 0 and dlog_p < dlog_t:   # both fell, prog fell more
            driver = "denominator collapse (test also sacrificed)"
        else:
            driver = "mixed"
        out.append({"variant": v, "test": t, "prog": p,
                    "cort": (c if c == c else None),
                    "test_vs_wt": t / wt_t, "prog_vs_wt": p / wt_p,
                    "ratio": t / p, "dlogT": dlog_t, "dlogP": dlog_p,
                    "dS": dS, "driver": driver})
    return {"wt_test": wt_t, "wt_prog": wt_p, "wt_ratio": wt_t / wt_p,
            "s_wt": s_wt, "rows": out}


def write():
    d = decompose()
    L = ["# Singles decomposition — test gain vs progesterone collapse?",
         "",
         "_Round-0 single-dose GFP fold (`results/stage1f_empirical/scan_model_numbering.csv`). "
         "Answers the minicrew debate's decisive question before any multi-mutant build._",
         "",
         f"**WT:** testosterone={d['wt_test']:.0f}, progesterone={d['wt_prog']:.0f}, "
         f"test/prog={d['wt_ratio']:.2f}.",
         "",
         "| variant | test | prog | cort | test/prog | test vs WT | prog vs WT | Δlog test | Δlog prog | driver of selectivity |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in d["rows"]:
        cort = f"{r['cort']:.0f}" if r["cort"] is not None else "—"
        L.append(f"| {r['variant']} | {r['test']:.0f} | {r['prog']:.1f} | {cort} | "
                 f"{r['ratio']:.1f} | {r['test_vs_wt']*100:.0f}% | {r['prog_vs_wt']*100:.0f}% | "
                 f"{r['dlogT']:+.2f} | {r['dlogP']:+.2f} | {r['driver']} |")
    # verdict
    good = [r["variant"] for r in d["rows"] if r["driver"].startswith("GOOD")]
    collapse = [r["variant"] for r in d["rows"]
                if "collapse" in r["driver"]]
    L += ["",
          "## Verdict",
          f"- **Testosterone retained (good lever):** {', '.join(good) or 'none'} — "
          "selectivity gained by suppressing progesterone while keeping the testosterone signal.",
          f"- **Denominator collapse (testosterone also sacrificed):** {', '.join(collapse) or 'none'} — "
          "selectivity is largely the progesterone signal falling toward baseline; absolute testosterone "
          "induction drops too, so stacking risks a dim/dead sensor.",
          "",
          "**Implication for round-1/round-2:** favour combinations built on the test-retaining lever(s); "
          "treat collapse-type singles as risky to stack (negative-epistasis / dead-sensor risk). The round-1 "
          "diagnostic should read **absolute amplitude**, not just the fold ratio, for every variant."]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write("\n".join(L))
    return d, OUT


if __name__ == "__main__":
    d, out = write()
    print(f"WT test={d['wt_test']:.0f} prog={d['wt_prog']:.0f} ratio={d['wt_ratio']:.2f}\n")
    print(f"{'variant':7s} {'test':>5s} {'prog':>5s} {'t/p':>5s} {'t%WT':>5s} {'p%WT':>5s} "
          f"{'dlogT':>6s} {'dlogP':>6s}  driver")
    for r in d["rows"]:
        print(f"{r['variant']:7s} {r['test']:5.0f} {r['prog']:5.1f} {r['ratio']:5.1f} "
              f"{r['test_vs_wt']*100:4.0f}% {r['prog_vs_wt']*100:4.0f}% "
              f"{r['dlogT']:+6.2f} {r['dlogP']:+6.2f}  {r['driver']}")
    print(f"\nwrote {out}")
