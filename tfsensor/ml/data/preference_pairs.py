"""Within-pocket relative binding-preference pairs (the training signal).

Per the strategic pivot, the model's target is **relative binding preference**
(which of two ligands binds the same pocket more strongly) rather than absolute
affinity or allosteric activation. The cleanest large label source is ChEMBL:
within one receptor, every pair of measured ligands gives a preference label from
their ΔpKd.

Pairs are formed only **within the same (receptor, split)** so the split's
leakage guarantee carries over to the pairwise task. A magnitude floor (``margin``
on ΔpKd) drops near-ties that would only add label noise.

Reads the assembled manifest (must have run build_dataset.py + splits.py), uses
its ChEMBL rows (which carry receptor, pchembl, split).

Run:
    PYTHONPATH=. ~/LC-Seed/envs/app/.venv/bin/python -m tfsensor.ml.data.preference_pairs \
        --manifest data/ml/dataset_manifest.csv --out data/ml/preference_pairs.csv
"""
from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from itertools import combinations

DEFAULT_MARGIN = 0.5     # min |ΔpKd| for a pair to count (≈ 3x affinity)
DEFAULT_MAX_PER_GROUP = 4000


def load_chembl_rows(manifest):
    rows = []
    for r in csv.DictReader(open(manifest)):
        if r.get("source") != "chembl" or r.get("pchembl") in (None, ""):
            continue
        try:
            r["pchembl"] = float(r["pchembl"])
        except ValueError:
            continue
        rows.append(r)
    return rows


def make_pairs(rows, margin=DEFAULT_MARGIN, max_per_group=DEFAULT_MAX_PER_GROUP):
    """Form within-(receptor,split) preference pairs.

    label = 1 if ligand A binds more strongly than B (higher pKd), else 0.
    Always ordered so the listed (A,B) has a definite preference (skips ties).
    """
    groups = defaultdict(list)
    for r in rows:
        groups[(r["receptor"], r.get("split", "?"))].append(r)

    pairs = []
    for (receptor, split), items in groups.items():
        g = []
        for a, b in combinations(items, 2):
            d = a["pchembl"] - b["pchembl"]
            if abs(d) < margin:
                continue
            strong, weak = (a, b) if d > 0 else (b, a)
            g.append({
                "receptor": receptor,
                "split": split,
                "mol_strong": strong["uid"],
                "mol_weak": weak["uid"],
                "smiles_strong": strong["smiles"],
                "smiles_weak": weak["smiles"],
                "dpKd": round(abs(d), 3),
                "label": 1,           # by construction: strong > weak
            })
            if len(g) >= max_per_group:
                break
        pairs.extend(g)
    return pairs


def write_csv(pairs, out_path):
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    cols = ["receptor", "split", "mol_strong", "mol_weak", "smiles_strong",
            "smiles_weak", "dpKd", "label"]
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(pairs)


def _main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default="data/ml/dataset_manifest.csv")
    ap.add_argument("--out", default="data/ml/preference_pairs.csv")
    ap.add_argument("--margin", type=float, default=DEFAULT_MARGIN)
    args = ap.parse_args()

    rows = load_chembl_rows(args.manifest)
    pairs = make_pairs(rows, margin=args.margin)
    write_csv(pairs, args.out)

    from collections import Counter
    by_split = Counter(p["split"] for p in pairs)
    by_recep = Counter(p["receptor"] for p in pairs)
    print(f"{len(rows)} ChEMBL ligands -> {len(pairs)} preference pairs "
          f"(|ΔpKd|>={args.margin}) -> {args.out}")
    print("  by split:", dict(by_split))
    print("  by receptor:", dict(by_recep))


if __name__ == "__main__":
    _main()
