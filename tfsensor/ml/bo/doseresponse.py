"""Dose-response objective for the DBTL loop (panel must-fix #5, 2026-06-22).

The bo_plan_review panel showed the round-0 SINGLE-DOSE fold misranks variants
(operating ranges differ: WT 1-100 uM vs L147R 1-5 uM) and conflates basal leak
with induction (A66M basal 130k = fake "signal"). From round-1 on, the TRUSTED
objective is a per-(variant, steroid) dose-response fit:

    signal(dose) = basal + amplitude / (1 + (EC50/dose)**hill)        (agonist Hill)

From the fit we take INDUCTION AMPLITUDE (basal subtracted by construction), the
EC50 (operating range), and the fit/replicate variance. Selectivity is then an
amplitude ratio with an operating-range sanity check, and its variance is
propagated so the surrogate can down-weight noise-floor margins (heteroscedastic
GP `Yvar`). `y2` (sensor quality / allosteric amplitude) is NOT a predicted
objective -- per the panel it stays a wet-lab-measured constraint.

Plate CSV schema (tidy, one row per well):
    variant, steroid, dose_uM, replicate, signal[, is_basal]
`dose_uM == 0` (or is_basal truthy) marks a no-ligand basal well.

Needs numpy + scipy (e.g. ~/.conda/envs/TF_agent_env). Pure-analysis, no GPU.
"""
from __future__ import annotations

import csv
import math
import os
from collections import defaultdict

import numpy as np

from tfsensor.ml.bo.seed import EPS, PRIMARY  # reuse target conventions

# default campaign target (committed 2026-06-22 per panel recommendation)
DEFAULT_TARGET = "testosterone"
DEFAULT_OFFTARGETS = ["progesterone", "estradiol", "cortisol"]


def hill(dose, basal, amplitude, ec50, n):
    """Agonist Hill: basal + amplitude / (1 + (ec50/dose)**n). dose>0."""
    dose = np.asarray(dose, dtype=float)
    return basal + amplitude / (1.0 + (ec50 / np.maximum(dose, 1e-12)) ** n)


def fit_dose_response(doses, signals, basal_signals=None):
    """Fit the 4-param Hill to one (variant, steroid) dose series.

    doses, signals: arrays over all non-basal wells (replicates included).
    basal_signals: optional no-ligand wells -> anchors `basal` and its variance.

    Returns dict: basal, amplitude, ec50, hill, amplitude_sd, ec50_in_range,
    n_doses, r2, quality ('full'|'single_dose'|'flat'|'failed').
    """
    doses = np.asarray(doses, dtype=float)
    signals = np.asarray(signals, dtype=float)
    ok = np.isfinite(doses) & np.isfinite(signals) & (doses > 0)
    doses, signals = doses[ok], signals[ok]
    uniq = np.unique(doses)

    basal0 = (float(np.mean(basal_signals)) if basal_signals is not None
              and len(basal_signals) else float(signals.min()) if len(signals) else 0.0)
    basal_sd = (float(np.std(basal_signals, ddof=1)) if basal_signals is not None
                and len(basal_signals) > 1 else 0.0)

    if len(uniq) < 2:
        # single-dose fallback: amplitude = best-dose mean - basal (low confidence)
        amp = float(np.mean(signals) - basal0) if len(signals) else 0.0
        sd = float(np.std(signals, ddof=1)) if len(signals) > 1 else abs(amp)
        return {"basal": basal0, "amplitude": amp, "ec50": float("nan"),
                "hill": float("nan"), "amplitude_sd": math.hypot(sd, basal_sd),
                "ec50_in_range": False, "n_doses": int(len(uniq)),
                "r2": float("nan"), "quality": "single_dose"}

    from scipy.optimize import curve_fit
    span = signals.max() - signals.min()
    p0 = [basal0, max(span, 1.0), float(np.median(uniq)), 1.0]
    lo = [-np.inf, 0.0, uniq.min() * 1e-3, 0.3]
    hi = [np.inf, np.inf, uniq.max() * 1e3, 6.0]
    try:
        popt, pcov = curve_fit(hill, doses, signals, p0=p0, bounds=(lo, hi),
                               maxfev=20000)
    except Exception:
        return {"basal": basal0, "amplitude": float("nan"), "ec50": float("nan"),
                "hill": float("nan"), "amplitude_sd": float("inf"),
                "ec50_in_range": False, "n_doses": int(len(uniq)),
                "r2": float("nan"), "quality": "failed"}
    basal, amp, ec50, n = popt
    resid = signals - hill(doses, *popt)
    ss_res, ss_tot = float(resid @ resid), float(((signals - signals.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    amp_sd = float(math.sqrt(max(pcov[1, 1], 0.0))) if np.all(np.isfinite(pcov)) else float("inf")
    amp_sd = math.hypot(amp_sd, basal_sd)
    in_range = bool(uniq.min() <= ec50 <= uniq.max())
    quality = "flat" if amp < 2 * (amp_sd + 1e-9) else "full"
    return {"basal": float(basal), "amplitude": float(amp), "ec50": float(ec50),
            "hill": float(n), "amplitude_sd": amp_sd, "ec50_in_range": in_range,
            "n_doses": int(len(uniq)), "r2": float(r2), "quality": quality}


def load_plate(csv_path):
    """Tidy plate CSV -> {variant: {steroid: {'doses':[], 'signals':[], 'basal':[]}}}."""
    table = defaultdict(lambda: defaultdict(lambda: {"doses": [], "signals": [], "basal": []}))
    with open(csv_path) as fh:
        for r in csv.DictReader(fh):
            v, s = r["variant"].strip(), r["steroid"].strip()
            sig = float(r["signal"])
            dose = float(r.get("dose_uM", 0) or 0)
            is_basal = str(r.get("is_basal", "")).strip().lower() in ("1", "true", "yes")
            cell = table[v][s]
            if is_basal or dose <= 0:
                cell["basal"].append(sig)
            else:
                cell["doses"].append(dose)
                cell["signals"].append(sig)
    return table


def fit_plate(csv_path):
    """{variant: {steroid: fit_dict}} for every (variant, steroid) in the plate."""
    table = load_plate(csv_path)
    out = {}
    for v, by_steroid in table.items():
        out[v] = {}
        for s, cell in by_steroid.items():
            out[v][s] = fit_dose_response(cell["doses"], cell["signals"],
                                          cell["basal"] or None)
    return out


def selectivity_from_fits(fits, target=DEFAULT_TARGET, offtargets=None, eps=EPS):
    """Amplitude-based selectivity + propagated variance for one variant.

    y1 = log10( max(amp_target, eps) / max(max_offtarget_amp, eps) ), with the
    off-target taken over fits present. Returns (y1, y1_var, flags) or None.
    Variance via the delta method on log10 of each amplitude.
    """
    if offtargets is None:
        offtargets = [s for s in PRIMARY if s != target]
    ft = fits.get(target)
    if ft is None or not np.isfinite(ft["amplitude"]):
        return None
    amp_t = max(ft["amplitude"], eps)
    offs = [(o, fits[o]) for o in offtargets if o in fits
            and np.isfinite(fits[o]["amplitude"])]
    if offs:
        o_name, o_fit = max(offs, key=lambda kv: kv[1]["amplitude"])
        amp_o = max(o_fit["amplitude"], eps)
        sd_o = o_fit["amplitude_sd"]
    else:
        o_name, amp_o, sd_o = None, eps, 0.0
    y1 = math.log10(amp_t / amp_o)
    ln10 = math.log(10.0)
    # var(log10 x) ~= (sd/x)^2 / ln10^2 ; sum for the ratio (independent fits)
    var_t = (ft["amplitude_sd"] / max(amp_t, eps)) ** 2 / ln10 ** 2
    var_o = (sd_o / max(amp_o, eps)) ** 2 / ln10 ** 2
    y1_var = float(var_t + var_o)
    flags = {"target_ec50_in_range": ft["ec50_in_range"],
             "target_quality": ft["quality"], "best_offtarget": o_name}
    return y1, y1_var, flags


def objective_table(csv_path, target=DEFAULT_TARGET, offtargets=None, eps=EPS):
    """Round-1+ analogue of seed.objective_table, on dose-response data.

    Returns (variants, y, yvar, flags) -- yvar feeds the GP as heteroscedastic noise.
    """
    fits = fit_plate(csv_path)
    variants, y, yvar, flags = [], [], [], []
    for v in fits:
        res = selectivity_from_fits(fits[v], target, offtargets, eps)
        if res is None:
            continue
        y1, y1_var, fl = res
        variants.append(v); y.append(y1); yvar.append(y1_var); flags.append(fl)
    return variants, y, yvar, flags


def _selftest():
    """No real dose-response plate exists yet -> validate on synthetic data."""
    print("=== doseresponse self-test (synthetic) ===")
    doses = np.array([0.1, 0.3, 1, 3, 10, 30, 100] * 3)
    # a clean testosterone-selective double: strong test induction, weak prog
    rng = np.random.default_rng(0)
    sig_t = hill(doses, 500, 8000, 4.0, 1.2) + rng.normal(0, 150, doses.size)
    sig_p = hill(doses, 500, 1200, 20.0, 1.0) + rng.normal(0, 150, doses.size)
    basal = [480, 510, 495]
    ft = fit_dose_response(doses, sig_t, basal)
    fp = fit_dose_response(doses, sig_p, basal)
    print(f"  testosterone fit: amp={ft['amplitude']:.0f} EC50={ft['ec50']:.2f} "
          f"r2={ft['r2']:.3f} q={ft['quality']}")
    print(f"  progesterone fit: amp={fp['amplitude']:.0f} EC50={fp['ec50']:.2f} "
          f"r2={fp['r2']:.3f} q={fp['quality']}")
    fits = {"testosterone": ft, "progesterone": fp}
    y1, var, fl = selectivity_from_fits(fits, "testosterone", ["progesterone"])
    print(f"  selectivity y1={y1:+.3f} +- {math.sqrt(var):.3f}  flags={fl}")
    assert ft["amplitude"] > fp["amplitude"] and y1 > 0, "expected test>prog selectivity"
    # single-dose fallback degrades gracefully
    sd = fit_dose_response([10, 10, 10], [8000, 8200, 7900], basal)
    assert sd["quality"] == "single_dose"
    print(f"  single-dose fallback: amp={sd['amplitude']:.0f} q={sd['quality']}  OK")
    print("PASS")


if __name__ == "__main__":
    _selftest()
