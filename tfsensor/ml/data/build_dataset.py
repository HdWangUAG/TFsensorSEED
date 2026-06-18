"""Assemble the unified steroid-binding dataset manifest.

Two label regimes are merged into one manifest (the multi-task model consumes
whatever labels each row carries):

  * STRUCTURAL rows (LC-SEED) — have a PDB structure + pocket + (often) contacts;
    the co-crystallised steroid is a presumed binder. No measured affinity.
  * AFFINITY rows (ChEMBL NR) — have SMILES + receptor + pKd/ΔG + binder label.
    No structure.

Per row we also compute a Bemis–Murcko scaffold (for scaffold-split stress tests)
and a ``group_key`` used by :mod:`tfsensor.ml.data.splits` to make leakage-safe
train/val/test partitions:
    structural -> "cath:<primary CATH family>"  (fallback "pdb:<id>")
    affinity   -> "nr:<receptor>"

Run in an rdkit env:
    ~/LC-Seed/envs/app/.venv/bin/python -m tfsensor.ml.data.build_dataset \
        --lcseed data/ml/lcseed_steroid_complexes.csv \
        --chembl data/ml/nr_datasets/chembl_nr_steroids.csv \
        --out data/ml/dataset_manifest.csv
"""
from __future__ import annotations

import argparse
import csv
import os

from rdkit import Chem, RDLogger
from rdkit.Chem.Scaffolds import MurckoScaffold

RDLogger.DisableLog("rdApp.*")

COLS = ["uid", "source", "pdb", "ligand_code", "receptor", "smiles", "scaffold",
        "seq_hash", "group_key", "dG_kcalmol", "pchembl", "binder",
        "has_structure", "has_contacts"]


def murcko_scaffold(smiles):
    try:
        scf = MurckoScaffold.MurckoScaffoldSmiles(smiles)
        return scf or ""
    except Exception:
        return ""


def _primary_cath(cath_field):
    return cath_field.split(";")[0].strip() if cath_field else ""


def from_lcseed(path, dedup=True):
    """Structural rows from the LC-SEED mining CSV.

    group_key = seq_hash (identical protein sequences across PDB IDs share a
    split — defeats sequence leakage), falling back to CATH/pdb. With dedup,
    collapse identical (seq_hash, ligand_code) complexes to one representative
    (prefer one that carries contacts) so a protein solved N times with the same
    steroid counts once.
    """
    raw = list(csv.DictReader(open(path)))
    if dedup:
        best = {}
        for r in raw:
            seq = r.get("seq_hash", "") or f"pdb:{r['pdb']}"
            key = (seq, r["ligand_code"])
            cur = best.get(key)
            # prefer the representative that has pre-computed contacts
            if cur is None or (int(r.get("has_contacts", 0)) >
                               int(cur.get("has_contacts", 0))):
                best[key] = r
        raw = list(best.values())

    rows = []
    for i, r in enumerate(raw):
        cath = _primary_cath(r.get("cath", ""))
        seq = r.get("seq_hash", "")
        group = seq or (f"cath:{cath}" if cath else f"pdb:{r['pdb']}")
        rows.append({
            "uid": f"lcseed_{i}",
            "source": "lcseed",
            "pdb": r["pdb"],
            "ligand_code": r["ligand_code"],
            "receptor": cath,
            "smiles": r["smiles"],
            "scaffold": murcko_scaffold(r["smiles"]),
            "seq_hash": seq,
            "group_key": group,
            "dG_kcalmol": "",
            "pchembl": "",
            "binder": 1,                       # co-crystallised => presumed binder
            "has_structure": 1,
            "has_contacts": int(r.get("has_contacts") or 0),
        })
    return rows


def from_chembl(path):
    rows = []
    for i, r in enumerate(csv.DictReader(open(path))):
        rows.append({
            "uid": f"chembl_{i}",
            "source": "chembl",
            "pdb": "",
            "ligand_code": "",
            "receptor": r["target"],
            "smiles": r["smiles"],
            "scaffold": murcko_scaffold(r["smiles"]),
            "seq_hash": "",                    # affinity rows have no structure
            "group_key": f"nr:{r['target']}",
            "dG_kcalmol": r.get("dG_kcalmol", ""),
            "pchembl": r.get("pchembl", ""),
            "binder": r.get("binder", ""),
            "has_structure": 0,
            "has_contacts": 0,
        })
    return rows


def build(lcseed_csv, chembl_csv, dedup=True):
    rows = []
    if lcseed_csv and os.path.exists(lcseed_csv):
        rows += from_lcseed(lcseed_csv, dedup=dedup)
    if chembl_csv and os.path.exists(chembl_csv):
        rows += from_chembl(chembl_csv)
    return rows


def write_csv(rows, out_path):
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lcseed", default="data/ml/lcseed_steroid_complexes.csv")
    ap.add_argument("--chembl", default="data/ml/nr_datasets/chembl_nr_steroids.csv")
    ap.add_argument("--out", default="data/ml/dataset_manifest.csv")
    ap.add_argument("--no-dedup", action="store_true",
                    help="keep all PDB copies of the same (sequence, ligand)")
    args = ap.parse_args()

    rows = build(args.lcseed, args.chembl, dedup=not args.no_dedup)
    write_csv(rows, args.out)

    from collections import Counter
    src = Counter(r["source"] for r in rows)
    n_struct = sum(r["has_structure"] for r in rows)
    n_dG = sum(1 for r in rows if r["dG_kcalmol"] != "")
    n_groups = len({r["group_key"] for r in rows})
    n_scaf = len({r["scaffold"] for r in rows if r["scaffold"]})
    n_seq = len({r["seq_hash"] for r in rows if r["seq_hash"]})
    print(f"{len(rows)} rows -> {args.out}  (dedup={not args.no_dedup})")
    print(f"  by source: {dict(src)}")
    print(f"  with structure: {n_struct}; with ΔG: {n_dG}")
    print(f"  unique protein sequences (structural): {n_seq}")
    print(f"  split groups: {n_groups}; distinct scaffolds: {n_scaf}")


if __name__ == "__main__":
    _main()
