"""Nuclear-receptor steroid affinity labels from ChEMBL.

The structural steroid set (PDBbind) is tiny (~tens of clean complexes), so the
bulk of the labeled signal comes from sequence+affinity data. ChEMBL is fully
scriptable (no login) and spans the five canonical steroid receptors.

For each target we pull bioactivities that carry a ``pchembl_value`` (ChEMBL's
harmonised −log10(molar) over Ki/Kd/IC50/EC50/Potency), attach the ligand SMILES,
keep only steroids (gonane nucleus via :mod:`tfsensor.ml.data.steroid_filter`),
aggregate to one value per (target, molecule), and emit a tidy table with:

    dG_kcalmol = -1.364 * pchembl   (≈ −RT·ln K at 298 K, as for pKd)
    binder     = pchembl >= 5       (Kd/Ki/IC50 <= 10 µM)

This is a coarse label (mixes assay types) — ``standard_types`` is retained so a
stricter Ki/Kd-only subset can be taken later.

CLI (small validation pull, steroids only):
    ~/LC-Seed/envs/app/.venv/bin/python -m tfsensor.ml.data.nr_datasets \
        --max-per-target 1500 --out data/ml/nr_datasets/chembl_nr_steroids.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import time
import urllib.parse
import urllib.request

from tfsensor.ml.data.steroid_filter import is_steroid

API = "https://www.ebi.ac.uk/chembl/api/data/activity.json"

# Short name -> ChEMBL target id, for the five canonical steroid receptors.
NR_TARGETS = {
    "ESR1": "CHEMBL206",    # estrogen receptor alpha
    "ESR2": "CHEMBL242",    # estrogen receptor beta
    "AR":   "CHEMBL1871",   # androgen receptor
    "GR":   "CHEMBL2034",   # glucocorticoid receptor (NR3C1)
    "PR":   "CHEMBL208",    # progesterone receptor
    "MR":   "CHEMBL1994",   # mineralocorticoid receptor (NR3C2)
}

KCAL_PER_PCHEMBL = -1.364   # dG = -1.364 * pchembl (kcal/mol, 298 K)
BINDER_PCHEMBL = 5.0        # >= 5  <=>  Kd/Ki/IC50 <= 10 uM


def fetch_activities(target_id, max_records=None, page_size=1000,
                     organism="Homo sapiens", pause=0.2):
    """Yield ChEMBL activity records (with pchembl_value) for one target."""
    params = {
        "target_chembl_id": target_id,
        "pchembl_value__isnull": "false",
        "limit": page_size,
        "offset": 0,
    }
    url = API + "?" + urllib.parse.urlencode(params)
    n = 0
    while url:
        with urllib.request.urlopen(url, timeout=60) as fh:
            page = json.load(fh)
        for a in page.get("activities", []):
            if organism and a.get("target_organism") != organism:
                continue
            if not a.get("canonical_smiles") or a.get("pchembl_value") is None:
                continue
            yield a
            n += 1
            if max_records and n >= max_records:
                return
        nxt = page.get("page_meta", {}).get("next")
        url = ("https://www.ebi.ac.uk" + nxt) if nxt else None
        if url:
            time.sleep(pause)


def build_table(targets=None, max_per_target=None, steroids_only=True,
                page_size=1000):
    """Pull all targets, aggregate per (target, molecule), return list of rows."""
    targets = targets or NR_TARGETS
    # (target, molecule_chembl_id) -> aggregation bucket
    agg = {}
    for name, cid in targets.items():
        for a in fetch_activities(cid, max_records=max_per_target,
                                  page_size=page_size):
            smi = a["canonical_smiles"]
            if steroids_only and not is_steroid(smi):
                continue
            key = (name, a["molecule_chembl_id"])
            b = agg.setdefault(key, {
                "target": name, "target_chembl_id": cid,
                "molecule_chembl_id": a["molecule_chembl_id"],
                "smiles": smi, "pchembl": [], "types": set(),
            })
            try:
                b["pchembl"].append(float(a["pchembl_value"]))
            except (TypeError, ValueError):
                continue
            if a.get("standard_type"):
                b["types"].add(a["standard_type"])

    rows = []
    for b in agg.values():
        if not b["pchembl"]:
            continue
        pchembl = statistics.median(b["pchembl"])
        rows.append({
            "target": b["target"],
            "target_chembl_id": b["target_chembl_id"],
            "molecule_chembl_id": b["molecule_chembl_id"],
            "smiles": b["smiles"],
            "pchembl": round(pchembl, 3),
            "n_measurements": len(b["pchembl"]),
            "standard_types": ";".join(sorted(b["types"])),
            "dG_kcalmol": round(KCAL_PER_PCHEMBL * pchembl, 3),
            "binder": int(pchembl >= BINDER_PCHEMBL),
            "is_steroid": int(is_steroid(b["smiles"])),
        })
    rows.sort(key=lambda r: (r["target"], -r["pchembl"]))
    return rows


def write_csv(rows, out_path):
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    cols = ["target", "target_chembl_id", "molecule_chembl_id", "smiles",
            "pchembl", "n_measurements", "standard_types", "dG_kcalmol",
            "binder", "is_steroid"]
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def _main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-per-target", type=int, default=None,
                    help="cap activities pulled per target (for quick runs)")
    ap.add_argument("--all-molecules", action="store_true",
                    help="keep non-steroids too (default: steroids only)")
    ap.add_argument("--targets", nargs="*", default=None,
                    help="subset of %s" % ",".join(NR_TARGETS))
    ap.add_argument("--out", default="data/ml/nr_datasets/chembl_nr_steroids.csv")
    args = ap.parse_args()

    tgt = NR_TARGETS if not args.targets else {
        k: NR_TARGETS[k] for k in args.targets}
    rows = build_table(tgt, max_per_target=args.max_per_target,
                       steroids_only=not args.all_molecules)
    write_csv(rows, args.out)

    by_t = {}
    for r in rows:
        by_t.setdefault(r["target"], 0)
        by_t[r["target"]] += 1
    n_binder = sum(r["binder"] for r in rows)
    print(f"{len(rows)} rows ({n_binder} binders) -> {args.out}")
    for t in sorted(by_t):
        print(f"  {t:5s} {by_t[t]:5d}")


if __name__ == "__main__":
    _main()
