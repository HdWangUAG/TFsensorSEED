"""Sanity tests for eval metrics (synthetic data with known answers).

Run:
    PYTHONPATH=. ~/LC-Seed/envs/app/.venv/bin/python tfsensor/ml/tests/test_metrics.py
"""
from __future__ import annotations

import math

from tfsensor.ml.eval.metrics import (auroc, auprc, regression_metrics,
                                       pairwise_ranking_accuracy,
                                       within_group_spearman)


def test_regression_perfect():
    m = regression_metrics([1, 2, 3, 4], [1, 2, 3, 4])
    assert abs(m["pearson"] - 1.0) < 1e-9
    assert abs(m["spearman"] - 1.0) < 1e-9
    assert m["rmse"] < 1e-9 and m["mae"] < 1e-9


def test_auroc_perfect_and_random():
    # perfectly separable -> 1.0
    assert abs(auroc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) - 1.0) < 1e-9
    # perfectly anti-separable -> 0.0
    assert abs(auroc([1, 1, 0, 0], [0.1, 0.2, 0.8, 0.9]) - 0.0) < 1e-9


def test_auprc_all_positives_first():
    # positives ranked above negatives -> AP = 1.0
    assert abs(auprc([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1]) - 1.0) < 1e-9


def test_pairwise_ranking_acc():
    # one receptor group; true ΔG order A<B<C (A strongest, 'lower')
    groups = ["R", "R", "R"]
    y_true = [-10.0, -8.0, -6.0]
    y_pred = [-9.0, -7.5, -6.5]          # same order -> all pairs correct
    r = pairwise_ranking_accuracy(groups, y_true, y_pred, stronger="lower")
    assert r["n_pairs"] == 3 and abs(r["pairwise_acc"] - 1.0) < 1e-9
    # reversed predictions -> 0
    r2 = pairwise_ranking_accuracy(groups, y_true, [-6.5, -7.5, -9.0],
                                   stronger="lower")
    assert abs(r2["pairwise_acc"] - 0.0) < 1e-9


def test_within_group_spearman():
    groups = ["R"] * 4
    s = within_group_spearman(groups, [1, 2, 3, 4], [1, 2, 3, 4])
    assert s["n_groups"] == 1 and abs(s["mean_spearman"] - 1.0) < 1e-9


if __name__ == "__main__":
    test_regression_perfect()
    test_auroc_perfect_and_random()
    test_auprc_all_positives_first()
    test_pairwise_ranking_acc()
    test_within_group_spearman()
    print("OK: all metrics sanity tests passed")
