"""Interpretable pairwise binding-preference ranker (contact-difference logistic).

The deliverable of the pivot: predict which of two ligands a pocket prefers, with
a score that is interpretable by construction. Each ligand is featurized by its
core-aligned-pose contact fingerprint (residue-type × interaction-type). For a
within-pocket preference pair (strong > weak) the model sees the **contact
difference** x = fp(strong) − fp(weak) and learns a weight vector w via logistic
regression (no intercept; symmetric ±x pairs). Then:

    preference score(ligand | pocket) = w · fp(ligand)
    w_i > 0  ⇒  more of contact i (e.g. GLU:hbond) raises predicted binding

so w is the explanation — no post-hoc attribution needed for this model (the GNN
in Phase 3 will use Integrated Gradients for the same readout at higher fidelity).

numpy-only (no sklearn). Run:
    PYTHONPATH=. ~/LC-Seed/envs/app/.venv/bin/python -m tfsensor.ml.model.preference_ranker
"""
from __future__ import annotations

import argparse
import csv
import os
import signal

import numpy as np


class _Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise _Timeout()


def _featurize_with_timeout(fn, seconds=8):
    """Run fn() but abort if it exceeds `seconds` (RDKit embed can hang)."""
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(seconds)
    try:
        return fn()
    except _Timeout:
        return {"accepted": False, "reason": "timeout"}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)

from collections import defaultdict

from tfsensor.ml.features.contacts_fingerprint import FEATURE_NAMES
from tfsensor.ml.features.pose_contacts import (load_references,
                                                load_reference_assets,
                                                featurize_loaded)


def featurize_chembl(manifest, refs, cache=None):
    """{uid: fingerprint} for ChEMBL ligands posed onto their receptor reference.

    Groups ligands by receptor and loads each reference's mol + pocket atoms ONCE
    (not per ligand). Ligands whose core pose fails QC are dropped (the user's
    fallback to 2D features for that subset is a TODO hook).
    """
    if cache and os.path.exists(cache):
        d = np.load(cache, allow_pickle=True)
        return dict(zip(d["uids"], d["fps"])), {"cached": True}
    by_rec = defaultdict(list)
    for r in csv.DictReader(open(manifest)):
        if r["source"] == "chembl":
            by_rec[r["receptor"]].append(r)

    feats, rejected, no_ref = {}, [], 0
    for receptor, rows in by_rec.items():
        ref = refs.get(receptor)
        if not ref:
            no_ref += len(rows)
            continue
        ref_mol, residues = load_reference_assets(
            ref["ligand_sdf"], ref["ref_pdb"], ref["pocket_json"])
        for i, r in enumerate(rows):
            res = _featurize_with_timeout(
                lambda: featurize_loaded(r["smiles"], ref_mol, residues))
            if res.get("accepted"):
                feats[r["uid"]] = res["fingerprint"]
            else:
                rejected.append(r["uid"])
            if (i + 1) % 50 == 0:
                print(f"  [{receptor}] {i+1}/{len(rows)} done, "
                      f"{len(feats)} featurized", flush=True)
    if cache:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        np.savez(cache, uids=np.array(list(feats)),
                 fps=np.array(list(feats.values())))
    return feats, {"n_featurized": len(feats), "n_rejected": len(rejected),
                   "n_no_ref": no_ref}


def build_xy(pairs_csv, feats, split):
    """Symmetric pairwise design matrix for one split: x=fp_strong-fp_weak (y=1) and -x (y=0)."""
    X, y = [], []
    for p in csv.DictReader(open(pairs_csv)):
        if p["split"] != split:
            continue
        a, b = p["mol_strong"], p["mol_weak"]
        if a not in feats or b not in feats:
            continue
        d = feats[a] - feats[b]
        X.append(d); y.append(1)
        X.append(-d); y.append(0)
    return np.array(X, float), np.array(y, float)


def train_logreg(X, y, l2=1.0, iters=800, lr=0.2):
    """Logistic regression, no intercept (symmetric pairs), L2-regularised."""
    w = np.zeros(X.shape[1])
    m = len(y)
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-(X @ w)))
        grad = X.T @ (p - y) / m + l2 * w / m
        w -= lr * grad
    return w


def pairwise_accuracy(X, y, w):
    if len(y) == 0:
        return float("nan"), 0
    pred = (X @ w > 0).astype(float)
    return float((pred == y).mean()), len(y) // 2


def top_features(w, k=10):
    idx = np.argsort(w)
    pos = [(FEATURE_NAMES[i], round(float(w[i]), 3)) for i in idx[::-1][:k]]
    neg = [(FEATURE_NAMES[i], round(float(w[i]), 3)) for i in idx[:k]]
    return pos, neg


def _main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default="data/ml/dataset_manifest.csv")
    ap.add_argument("--pairs", default="data/ml/preference_pairs.csv")
    ap.add_argument("--cache", default="data/ml/cache/chembl_pose_fp.npz")
    ap.add_argument("--l2", type=float, default=1.0)
    args = ap.parse_args()

    refs = load_references()
    feats, stats = featurize_chembl(args.manifest, refs, cache=args.cache)
    print(f"featurized ChEMBL ligands: {len(feats)}  ({stats})")

    Xtr, ytr = build_xy(args.pairs, feats, "train")
    print(f"train pairs (×2 symmetric): {len(ytr)}")
    if len(ytr) == 0:
        print("no trainable pairs (need featurized ligands on both sides)")
        return
    w = train_logreg(Xtr, ytr, l2=args.l2)

    for split in ("train", "val", "test"):
        X, y = build_xy(args.pairs, feats, split)
        acc, npairs = pairwise_accuracy(X, y, w)
        print(f"  {split:5s} pairwise_acc={acc:.3f}  (n_pairs={npairs})")

    pos, neg = top_features(w)
    print("\ninterpretable weights — contacts that RAISE binding preference:")
    for name, val in pos:
        print(f"  +{val:6.3f}  {name}")
    print("contacts that LOWER binding preference:")
    for name, val in neg:
        print(f"  {val:6.3f}  {name}")


if __name__ == "__main__":
    _main()
