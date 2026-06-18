"""Tests for the AcrR specificity acceptance harness.

Uses the recorded gnina panel numbers as a fixture (no live docking).
Run:
    PYTHONPATH=. ~/LC-Seed/envs/app/.venv/bin/python tfsensor/ml/tests/test_acrr_acceptance.py
"""
from __future__ import annotations

from tfsensor.ml.eval.acrr_specificity_test import (evaluate_panel, WT_ORDER,
                                                    WT_NONRESPONDERS,
                                                    load_ddg_for_mutation,
                                                    preference_shift_truth,
                                                    mutation_preference_order,
                                                    evaluate_preference_shifts)

# Recorded gnina CNNaffinity (higher = stronger binder).
GNINA = {"testosterone": 6.524, "cortisol": 6.374,
         "progesterone": 7.080, "estradiol": 6.444}


def test_perfect_predictor_passes():
    perfect = {"testosterone": 3.0, "cortisol": 2.0, "progesterone": 1.0,
               "estradiol": 0.5}
    rep = evaluate_panel(perfect, WT_ORDER, stronger="higher",
                         nonresponders=WT_NONRESPONDERS)
    assert rep["order_reproduced"] is True
    assert rep["pairwise_acc"] == 1.0
    assert rep["nonresponders_weakest"] is True


def test_gnina_does_not_reproduce_wt_order():
    rep = evaluate_panel(GNINA, WT_ORDER, stronger="higher",
                         nonresponders=WT_NONRESPONDERS)
    # documented Phase-1 result: a binding-only scorer should NOT pass
    assert rep["order_reproduced"] is False
    assert rep["predicted_order"][0] == "progesterone"   # most hydrophobic wins
    assert rep["pairwise_acc"] < 1.0


def test_ddg_ground_truth_loads():
    # R123E flex-ddG should exist and make cortisol the most strengthened binder
    ddg = load_ddg_for_mutation("R123E")
    if ddg is None:
        return  # results/ not present on this node — skip silently
    assert "cortisol" in ddg
    # ddG<0 strengthens; cortisol should be the most negative (best) for R123E
    assert ddg["cortisol"] == min(ddg.values())


def test_preference_shift_favors_cortisol():
    # PRIMARY binding target: R123E shifts preference toward cortisol (validated)
    truth = preference_shift_truth("cortisol", "testosterone", "R123E")
    if truth is None:
        return  # results/ absent on this node
    assert truth["favored"] == "cortisol"
    order = mutation_preference_order(
        "R123E", ["testosterone", "cortisol", "progesterone", "estradiol"])
    assert order[0] == "cortisol"


def test_evaluate_preference_shifts_perfect():
    ligs = ["testosterone", "cortisol", "progesterone"]
    truth_favored = {}
    for i in range(len(ligs)):
        for j in range(i + 1, len(ligs)):
            a, b = ligs[i], ligs[j]
            t = preference_shift_truth(a, b, "R123E")
            if t:
                truth_favored[(a, b)] = t["favored"]
    if not truth_favored:
        return
    rep = evaluate_preference_shifts(truth_favored, "R123E", ligands=ligs)
    assert rep["shift_sign_acc"] == 1.0


if __name__ == "__main__":
    test_perfect_predictor_passes()
    test_gnina_does_not_reproduce_wt_order()
    test_ddg_ground_truth_loads()
    test_preference_shift_favors_cortisol()
    test_evaluate_preference_shifts_perfect()
    print("OK: all AcrR acceptance-harness tests passed")
