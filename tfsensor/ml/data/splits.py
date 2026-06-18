"""Leakage-safe train/val/test splits for the steroid-binding manifest.

Random splits inflate protein–ligand benchmarks (Volkov 2022; LP-PDBBind). We
split by a similarity key and assign *whole groups* to one partition, using a
different key per label regime so each is controlled on its most relevant axis:

  * STRUCTURAL rows  -> by CATH family (group_key) — prevents protein-family leakage.
  * AFFINITY rows    -> by Bemis–Murcko scaffold — prevents ligand leakage, and
                        (with only ~6 NR receptors) still spreads affinity data
                        across all three splits so val/test can be evaluated.

Assignment is deterministic (md5 of the key → bucket), so reruns are stable
without needing a stored seed. A leakage report is printed and the split column
is written back to the manifest.

Run in any python:
    ~/LC-Seed/envs/app/.venv/bin/python -m tfsensor.ml.data.splits \
        --manifest data/ml/dataset_manifest.csv --out data/ml/dataset_manifest.csv
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict

DEFAULT_FRACTIONS = (0.8, 0.1, 0.1)  # train, val, test


def _bucket(key, fractions):
    """Deterministic [0,1) from a string key -> 'train'/'val'/'test'."""
    h = hashlib.md5(key.encode()).hexdigest()
    x = int(h[:8], 16) / 0xFFFFFFFF
    train, val, _ = fractions
    if x < train:
        return "train"
    if x < train + val:
        return "val"
    return "test"


def split_key(row):
    """The key whose whole group stays in one partition (regime-dependent)."""
    if row["source"] == "chembl":
        return "scaf:" + (row.get("scaffold") or row["smiles"])
    return row.get("group_key") or ("pdb:" + row.get("pdb", ""))


def assign_splits(rows, fractions=DEFAULT_FRACTIONS, holdout_keys=None):
    holdout = set(holdout_keys or [])
    for r in rows:
        k = split_key(r)
        r["split"] = "test" if k in holdout else _bucket(k, fractions)
    return rows


def leakage_report(rows):
    """Return (report_dict, ok). ok=False if any split key spans >1 split."""
    key_to_splits = defaultdict(set)
    scaf_to_splits = defaultdict(set)
    for r in rows:
        key_to_splits[split_key(r)].add(r["split"])
        if r.get("scaffold"):
            scaf_to_splits[r["scaffold"]].add(r["split"])
    spanning = {k: sorted(s) for k, s in key_to_splits.items() if len(s) > 1}
    # scaffolds that appear in >1 split (informational cross-regime overlap)
    scaf_overlap = sum(1 for s in scaf_to_splits.values() if len(s) > 1)

    by_split = defaultdict(lambda: Counter())
    for r in rows:
        s = r["split"]
        by_split[s]["n"] += 1
        by_split[s][r["source"]] += 1
        if r["dG_kcalmol"] != "":
            by_split[s]["with_dG"] += 1
    report = {
        "split_key_violations": spanning,
        "scaffold_cross_split_overlap": scaf_overlap,
        "by_split": {s: dict(c) for s, c in by_split.items()},
    }
    return report, (len(spanning) == 0)


def _main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default="data/ml/dataset_manifest.csv")
    ap.add_argument("--out", default="data/ml/dataset_manifest.csv")
    ap.add_argument("--fractions", default="0.8,0.1,0.1")
    args = ap.parse_args()

    fr = tuple(float(x) for x in args.fractions.split(","))
    rows = list(csv.DictReader(open(args.manifest)))
    assign_splits(rows, fractions=fr)
    report, ok = leakage_report(rows)

    cols = list(rows[0].keys())
    if "split" not in cols:
        cols.append("split")
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    print(f"leakage-safe split -> {args.out}   (no-leak: {ok})")
    for s in ("train", "val", "test"):
        c = report["by_split"].get(s, {})
        print(f"  {s:5s} n={c.get('n',0):5d}  lcseed={c.get('lcseed',0):5d}  "
              f"chembl={c.get('chembl',0):4d}  with_ΔG={c.get('with_dG',0):4d}")
    print(f"  scaffold cross-split overlap (informational): "
          f"{report['scaffold_cross_split_overlap']}")
    if not ok:
        print(f"  !! {len(report['split_key_violations'])} split-key violations")


if __name__ == "__main__":
    _main()
