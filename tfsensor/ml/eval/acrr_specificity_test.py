"""AcrR acceptance test — relative binding-preference shifts (post-pivot).

Per the strategic pivot, the predictor's target is **relative binding preference**
— specifically how a point mutation *shifts* the preference between two ligands in
the same pocket (a ΔΔΔG quantity), NOT allosteric activation. The trusted ground
truth is flex-ddG (results/stage3_ddg/ddg_results.json), sign convention
``ddG<0 = mutation strengthens binding``:

    preference shift of mutation M between ligands A,B  =  ddG(M,A) − ddG(M,B)
    shift < 0  ⇒  M favors A over B (strengthens A more / weakens A less)

flex-ddG covers R123E, R123D, F119W, L147R. Both R123E and L147R favor **cortisol**
(argmin ddG) — matching the validated "R123E/L147R → cortisol" result. A model
passes by reproducing these shift SIGNS (not absolute kcal; FEP resolves only
~1 kcal/mol).

Two things this harness deliberately separates:
  * PRIMARY (binding target): preference-shift sign vs flex-ddG ΔΔΔG — `evaluate_preference_shifts`.
  * INFORMATIONAL (functional readout, NOT a binding target): the WT activation
    order test>cort>prog — `evaluate_panel`. A binding-only scorer is not expected
    to reproduce activation, and saying so is a valid negative result.

Usage:
    from tfsensor.ml.eval.acrr_specificity_test import evaluate_preference_shifts
    # model_favored maps an (A,B) tuple -> the ligand the model predicts is favored
    rep = evaluate_preference_shifts(model_favored, "R123E")
"""
from __future__ import annotations

import json
import os

from tfsensor import config
from tfsensor.ml.eval.metrics import pairwise_ranking_accuracy

# Established functional orders (strongest -> weakest responder).
WT_ORDER = ["testosterone", "cortisol", "progesterone"]
WT_NONRESPONDERS = ["estradiol"]
R123E_TOP = "cortisol"
L147R_ORDER = ["cortisol", "progesterone", "testosterone"]

DDG_PATH = os.path.join(config.REPO_ROOT, "results/stage3_ddg/ddg_results.json")


def evaluate_panel(scores, expected_order, stronger="higher",
                   nonresponders=None):
    """Score a predictor's panel output against an expected functional order.

    scores: {ligand_name: value}. stronger: 'higher' (e.g. CNNaffinity/pKd/prob)
    or 'lower' (ΔG). Returns a report dict with pairwise ranking accuracy over the
    expected order, whether the full order is reproduced, and (if given) whether
    the non-responders are ranked weakest.
    """
    order = [l for l in expected_order if l in scores]
    # synthetic "true" rank values following the expected order, in the same
    # direction as `stronger`, so metrics agree with the predictor's convention.
    truth = {l: (len(order) - i) for i, l in enumerate(order)}  # higher = stronger
    if stronger == "lower":
        truth = {l: -v for l, v in truth.items()}
    groups = ["AcrR"] * len(order)
    pr = pairwise_ranking_accuracy(groups, [truth[l] for l in order],
                                   [scores[l] for l in order], stronger=stronger)

    pred_sorted = sorted(order, key=lambda l: scores[l],
                         reverse=(stronger == "higher"))
    order_ok = pred_sorted == order

    report = {
        "expected_order": order,
        "predicted_order": pred_sorted,
        "order_reproduced": order_ok,
        "pairwise_acc": pr["pairwise_acc"],
        "n_pairs": pr["n_pairs"],
    }
    nonresponders = nonresponders or []
    nr = [l for l in nonresponders if l in scores]
    if nr:
        weakest_val = min(scores[l] for l in order) if stronger == "higher" \
            else max(scores[l] for l in order)
        report["nonresponders_weakest"] = all(
            (scores[l] <= weakest_val) if stronger == "higher"
            else (scores[l] >= weakest_val) for l in nr)
    return report


def load_ddg_for_mutation(mutation, path=DDG_PATH):
    """Return {ligand: mean ddG} for a mutation from flex-ddG ground truth.

    ddG<0 = mutation strengthens binding (sign convention in the file).
    """
    if not os.path.exists(path):
        return None
    d = json.load(open(path))
    block = d.get("ddg", {}).get(mutation)
    if not block:
        return None
    return {lig: v["mean"] for lig, v in block.items()}


# --- PRIMARY: ΔΔΔG preference-shift ground truth & evaluation ---------------

def preference_shift_truth(lig_a, lig_b, mutation, path=DDG_PATH):
    """Ground-truth preference shift of `mutation` between two ligands.

    Returns {"shift_ddG": ddG(A)-ddG(B), "favored": <ligand>} or None if absent.
    shift<0 => mutation favors A over B.
    """
    ddg = load_ddg_for_mutation(mutation, path)
    if not ddg or lig_a not in ddg or lig_b not in ddg:
        return None
    shift = ddg[lig_a] - ddg[lig_b]
    return {"shift_ddG": shift, "favored": lig_a if shift < 0 else lig_b}


def mutation_preference_order(mutation, ligands=None, path=DDG_PATH):
    """Ligands ordered most→least favored by the mutation (most negative ddG first)."""
    ddg = load_ddg_for_mutation(mutation, path)
    if not ddg:
        return None
    ligs = [l for l in (ligands or ddg.keys()) if l in ddg]
    return sorted(ligs, key=lambda l: ddg[l])


def evaluate_preference_shifts(model_favored, mutation, ligands=None, path=DDG_PATH):
    """Compare a model's predicted favored ligand per pair vs flex-ddG ground truth.

    model_favored: dict keyed by an (A,B) tuple (either order) -> the ligand the
    model predicts the mutation favors. Returns accuracy over all gradeable pairs.
    """
    ddg = load_ddg_for_mutation(mutation, path)
    if not ddg:
        return None
    ligs = [l for l in (ligands or ddg.keys()) if l in ddg]
    correct = total = 0
    details = []
    for i in range(len(ligs)):
        for j in range(i + 1, len(ligs)):
            a, b = ligs[i], ligs[j]
            truth = preference_shift_truth(a, b, mutation, path)["favored"]
            pred = model_favored.get((a, b)) or model_favored.get((b, a))
            if pred is None:
                continue
            total += 1
            ok = (pred == truth)
            correct += int(ok)
            details.append({"pair": (a, b), "truth": truth, "pred": pred, "ok": ok})
    return {"mutation": mutation, "n_pairs": total,
            "shift_sign_acc": (correct / total) if total else float("nan"),
            "details": details}


def _main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gnina", action="store_true",
                    help="run the gnina panel and evaluate it (live)")
    args = ap.parse_args()
    if args.gnina:
        from tfsensor.ml.baselines.gnina import run_panel
        res = run_panel()
        scores = {k: v["affinity_pK"] for k, v in res.items() if "affinity_pK" in v}
        rep = evaluate_panel(scores, WT_ORDER, stronger="higher",
                             nonresponders=WT_NONRESPONDERS)
        print("gnina CNNaffinity vs WT functional order:")
        print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    _main()
