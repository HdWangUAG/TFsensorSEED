"""Round-1 DIAGNOSTIC design for the testosterone>progesterone campaign.

Per the bo_plan_review panel (must-fix #6, 2026-06-22), round-1 is NOT a
BO-combinatorial round. It is one fully-controlled dose-response plate whose sole
job is to measure the two quantities the whole GP extrapolation depends on:

  1. EPISTASIS  -- is a validated double (I61L+L85I, I61L+Q88T) ADDITIVE in
     selectivity, or does it deviate? We emit the additive PRIOR from round-0
     singles; the plate measures the truth.
  2. ASSAY NOISE -- replicate variance per (variant, steroid), to set the
     heteroscedastic GP `Yvar` and the `EPS`/operating-range thresholds from data.

Variants: WT anchor, the validated testosterone singles + Q88T, the two named
doubles, and the existing build-and-test leads (des0039/44/60 = I61L+L85I core).
Steroids: all four primaries. Readout: dose-response (basal + >=6 doses), >=3
biological replicates, full controls (WT, no-ligand basal, validated responder,
estradiol non-responder).

Additive prior (selectivity log-space, from round-0 single-dose seed):
    y1_hat(double) ~= sum_i y1(single_i) - (k-1)*y1(WT)
This is the panel's "is the double additive?" null hypothesis -- a prior, not a
prediction to trust (round-0 is single-dose; the panel flagged it as misranking).

Pure-numpy / stdlib. Writes the build-list + deliverable under results/stage4_bo/.
"""
from __future__ import annotations

import json
import os

from tfsensor import config
from tfsensor.ml.bo import seed

OUT_DIR = os.path.join(config.REPO_ROOT, "results/stage4_bo")
TARGET = "testosterone"
OFFTARGETS = ["progesterone", "estradiol", "cortisol"]

# (label, [mutation tokens], rationale)
VARIANTS = [
    ("WT", [], "anchor / reference; qNEHVI reference point"),
    ("I61L", ["I61L"], "validated testosterone-selective single"),
    ("L85I", ["L85I"], "validated testosterone-selective single"),
    ("E106L", ["E106L"], "validated testosterone-selective single (top lead)"),
    ("Q88L", ["Q88L"], "D-ring lever single (in round-0 scan; des0000 component)"),
    ("Q88T", ["Q88T"], "designed D-ring lever (des0002; NOT in round-0 -> plate anchors it)"),
    ("I61L+L85I", ["I61L", "L85I"], "named double; core of des0039/44/60 -> epistasis test"),
    ("I61L+Q88L", ["I61L", "Q88L"], "fully round-0-anchored double -> clean additive test"),
    ("I61L+Q88T", ["I61L", "Q88T"], "named double (des0002); Q88T prior set by plate single"),
]
# existing build-and-test leads carrying the I61L+L85I core (PROGRESS deliverables)
LEADS = ["des0039", "des0044", "des0060"]

DOSES_UM = [0.0, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0]  # 0.0 = no-ligand basal
N_REPLICATES = 3
STEROIDS = [TARGET] + OFFTARGETS


def round0_selectivity(target=TARGET, offtargets=None):
    """{model_mut: round-0 single-dose y1} for every scan variant (incl WT)."""
    variants, _muts, y = seed.objective_table(target, offtargets)
    return dict(zip(variants, y))


def additive_prior(double_tokens, y0, target=TARGET):
    """Additive null for a multi-mutant in selectivity log-space.

    y1_hat = sum_i y1(single_i) - (k-1)*y1(WT). Returns (prediction, missing list).
    """
    wt = y0.get("WT", 0.0)
    parts, missing = [], []
    for tok in double_tokens:
        if tok in y0:
            parts.append(y0[tok])
        else:
            missing.append(tok)
    k = len(double_tokens)
    pred = sum(parts) - (k - 1) * wt if not missing else float("nan")
    return pred, missing


def design():
    y0 = round0_selectivity()
    rows = []
    for label, toks, why in VARIANTS:
        single_y1 = {t: round(y0[t], 3) for t in toks if t in y0}
        if len(toks) >= 2:
            pred, missing = additive_prior(toks, y0)
            epi = {"additive_prior_y1": round(pred, 3) if pred == pred else None,
                   "missing_singles": missing}
        else:
            epi = {}
        rows.append({"variant": label, "mutations": toks, "rationale": why,
                     "round0_y1": round(y0.get(label, float("nan")), 3)
                     if label in y0 else None,
                     "component_singles_y1": single_y1, **epi})
    n_variants = len(VARIANTS) + len(LEADS)
    n_doses = len(DOSES_UM)
    wells = n_variants * len(STEROIDS) * n_doses * N_REPLICATES
    plate96 = -(-wells // 96)        # ceil
    plate384 = -(-wells // 384)
    return {"target": TARGET, "offtargets": OFFTARGETS, "steroids": STEROIDS,
            "doses_uM": DOSES_UM, "n_replicates": N_REPLICATES,
            "variants": rows, "existing_leads": LEADS,
            "well_count": wells, "plates_96": plate96, "plates_384": plate384}


def write(out_dir=OUT_DIR):
    d = design()
    os.makedirs(out_dir, exist_ok=True)
    jpath = os.path.join(out_dir, "round1_diagnostic.json")
    with open(jpath, "w") as fh:
        json.dump(d, fh, indent=2)

    lines = ["# Round-1 DIAGNOSTIC — testosterone>progesterone (panel must-fix #6)",
             "",
             f"_Generated {config.REPO_ROOT.split('/')[-1]} · target **{d['target']}** "
             f"vs {', '.join(d['offtargets'])}_", "",
             "**Purpose (NOT a BO round):** measure EPISTASIS (are the validated "
             "doubles additive?) and ASSAY NOISE (replicate variance → heteroscedastic "
             "GP `Yvar`) directly, before any combinatorial design.", "",
             "## Assay",
             f"- **Steroids:** {', '.join(d['steroids'])} (all four primaries)",
             f"- **Dose-response:** {d['doses_uM']} µM (0 = no-ligand basal well)",
             f"- **Replicates:** ≥{d['n_replicates']} biological",
             "- **Readout:** GFP fold; fit 4-param Hill per (variant, steroid) "
             "(`tfsensor.ml.bo.doseresponse`) → basal, amplitude, EC50, Hill.",
             f"- **Scale:** {d['well_count']} wells → "
             f"{d['plates_96']}×96-well or {d['plates_384']}×384-well.", "",
             "## Controls (panel-required)",
             "- **WT** anchor (qNEHVI reference point).",
             "- **No-ligand basal** per variant (subtracted; kills A66M-style fake signal).",
             "- **Validated responder** (E106L / L85I / I61L) — positive control.",
             "- **Non-responder** (estradiol on every variant) — dead-ligand negative control.", "",
             "## Variants & epistasis prior",
             "Additive null `y1_hat = Σ y1(singleᵢ) − (k−1)·y1(WT)` from round-0 "
             "single-dose seed (a PRIOR — round-0 misranks; the plate measures truth).",
             "",
             "| variant | mutations | round-0 y1 | additive prior (doubles) | rationale |",
             "|---|---|---|---|---|"]
    for r in d["variants"]:
        mut = "+".join(r["mutations"]) or "—"
        prior = r.get("additive_prior_y1")
        prior_s = f"{prior:+.3f}" if isinstance(prior, (int, float)) else "—"
        r0 = r["round0_y1"]
        r0_s = f"{r0:+.3f}" if isinstance(r0, (int, float)) else "—"
        lines.append(f"| {r['variant']} | {mut} | {r0_s} | {prior_s} | {r['rationale']} |")
    lines += ["",
              f"**Plus existing build-and-test leads** (I61L+L85I core): "
              f"{', '.join(d['existing_leads'])} — see "
              f"`deliverables/AcrR_testosterone_sensor_designs.{{md,csv}}`.", "",
              "## Decision rule",
              "- **Doubles additive** (measured y1 ≈ prior, within replicate noise) → "
              "an additive surrogate + active learning is justified; revisit a GP.",
              "- **Strong positive epistasis** → combinatorial search has headroom a "
              "singles-only additive model misses (BO worth re-attempting on clean data).",
              "- **Negative epistasis / no responders** → pocket is saturated at k=2; "
              "stop combinatorial expansion, report the validated singles/leads.", ""]
    mdpath = os.path.join(out_dir, "round1_diagnostic.md")
    with open(mdpath, "w") as fh:
        fh.write("\n".join(lines))
    return jpath, mdpath, d


if __name__ == "__main__":
    j, m, d = write()
    print(f"wrote {m}\n      {j}")
    print(f"variants={len(d['variants'])}+{len(d['existing_leads'])} leads  "
          f"wells={d['well_count']}  ({d['plates_96']}×96 / {d['plates_384']}×384)")
    for r in d["variants"]:
        if r["mutations"] and len(r["mutations"]) >= 2:
            print(f"  {r['variant']:12s} additive prior y1={r.get('additive_prior_y1')}  "
                  f"components={r['component_singles_y1']}")
