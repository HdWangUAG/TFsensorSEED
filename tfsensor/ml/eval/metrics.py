"""Metrics for the four prediction targets.

Kept dependency-light (numpy + scipy.stats only — both in the LC-SEED app env),
so the eval harness runs anywhere without sklearn.

  * affinity     -> pearson, spearman, rmse, mae   (on ΔG or pKd)
  * binder       -> auroc, auprc                    (manual, rank-based)
  * specificity  -> within-receptor spearman + pairwise ranking accuracy
                    (the metric that matters for AcrR)

Convention: for affinity, "stronger binder" = MORE NEGATIVE ΔG (or HIGHER pKd).
The specificity helpers take an explicit ``stronger`` direction so either works.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy.stats import pearsonr, spearmanr


def regression_metrics(y_true, y_pred):
    y_true = np.asarray(y_true, float)
    y_pred = np.asarray(y_pred, float)
    if len(y_true) < 2:
        return {"n": int(len(y_true)), "pearson": float("nan"),
                "spearman": float("nan"), "rmse": float("nan"), "mae": float("nan")}
    err = y_pred - y_true
    return {
        "n": int(len(y_true)),
        "pearson": float(pearsonr(y_true, y_pred)[0]),
        "spearman": float(spearmanr(y_true, y_pred)[0]),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mae": float(np.mean(np.abs(err))),
    }


def auroc(y_true, scores):
    """Rank-based AUROC (Mann–Whitney). y_true in {0,1}; higher score => positive."""
    y_true = np.asarray(y_true, int)
    scores = np.asarray(scores, float)
    pos = scores[y_true == 1]
    neg = scores[y_true == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = scores.argsort()
    ranks = np.empty(len(scores), float)
    ranks[order] = np.arange(1, len(scores) + 1)
    # average ranks for ties
    _, inv, counts = np.unique(scores, return_inverse=True, return_counts=True)
    tie_mean = np.array([ranks[scores == v].mean() for v in np.unique(scores)])
    ranks = tie_mean[inv]
    sum_pos = ranks[y_true == 1].sum()
    return float((sum_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def auprc(y_true, scores):
    """Average precision (area under precision-recall), higher score => positive."""
    y_true = np.asarray(y_true, int)
    scores = np.asarray(scores, float)
    if y_true.sum() == 0:
        return float("nan")
    order = scores.argsort()[::-1]
    y = y_true[order]
    tp = np.cumsum(y)
    precision = tp / np.arange(1, len(y) + 1)
    recall = tp / y_true.sum()
    # sum precision over points where a new positive is retrieved
    ap, prev_recall = 0.0, 0.0
    for p, r in zip(precision, recall):
        ap += p * (r - prev_recall)
        prev_recall = r
    return float(ap)


def binder_metrics(y_true, scores):
    return {"n": int(len(y_true)), "n_pos": int(np.sum(y_true)),
            "auroc": auroc(y_true, scores), "auprc": auprc(y_true, scores)}


def pairwise_ranking_accuracy(groups, y_true, y_pred, stronger="lower"):
    """Fraction of within-group ligand pairs ordered correctly.

    groups: iterable of receptor/group ids (pairs are formed within a group).
    stronger: 'lower' if a smaller value = stronger binder (ΔG), 'higher' for pKd.
    Ties in y_true are skipped.
    """
    by_g = defaultdict(list)
    for g, t, p in zip(groups, y_true, y_pred):
        by_g[g].append((float(t), float(p)))
    sign = -1.0 if stronger == "lower" else 1.0
    correct = total = 0
    for items in by_g.values():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                ti, pi = items[i]
                tj, pj = items[j]
                if ti == tj:
                    continue
                total += 1
                # do predicted and true agree on which is stronger?
                if (sign * (pi - pj)) * (sign * (ti - tj)) > 0:
                    correct += 1
    return {"n_pairs": total,
            "pairwise_acc": (correct / total) if total else float("nan")}


def within_group_spearman(groups, y_true, y_pred):
    """Mean Spearman of predicted vs true, computed within each group (≥3 items)."""
    by_g = defaultdict(lambda: ([], []))
    for g, t, p in zip(groups, y_true, y_pred):
        by_g[g][0].append(t)
        by_g[g][1].append(p)
    rhos = []
    for t, p in by_g.values():
        if len(t) >= 3:
            rho = spearmanr(t, p)[0]
            if rho == rho:  # not nan
                rhos.append(rho)
    return {"n_groups": len(rhos),
            "mean_spearman": float(np.mean(rhos)) if rhos else float("nan")}
