"""Mine steroid–protein complexes from the local LC-SEED corpus.

The structural backbone of the dataset (plan: LC-SEED section). We enumerate the
steroid PDB ligand codes (CCD SMILES filtered by our gonane detector), then join
against LC-SEED's pre-computed maps in ``~/LC-Seed/static/dataset/``:

    biounit_ligand_map.json  -> every PDB (+chains) that binds each steroid code
    interactions_map.json    -> PLIP-style contacts per ligand instance (binding-mode labels)
    cath_domains.json        -> CATH family per chain (for leakage-safe splitting)

The heavyweight maps (pocket_metrics ~206 MB, protein_annotation ~186 MB) are left
to the featurization stage and not loaded here.

Emits one row per (pdb, ligand instance) for steroid ligands, with the SMILES and
the join metadata. No network; all local.

Run in an rdkit env:
    ~/LC-Seed/envs/app/.venv/bin/python -m tfsensor.ml.data.lcseed_mining \
        --ccd-smiles data/ml/cache/ccd_smiles.json \
        --out data/ml/lcseed_steroid_complexes.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os

from tfsensor import config
from tfsensor.ml.data.steroid_filter import is_steroid

DATASET_DIR = os.path.join(config.LC_SEED, "static/dataset")


def _load(name):
    with open(os.path.join(DATASET_DIR, name)) as fh:
        return json.load(fh)


def steroid_codes(ccd_smiles_path):
    """{pdb_code: smiles} restricted to steroids (gonane nucleus)."""
    smiles = json.load(open(ccd_smiles_path))
    return {code: smi for code, smi in smiles.items() if is_steroid(smi)}


def mine_steroid_complexes(ccd_smiles_path, attach=True):
    """Return (rows, steroid_code_map).

    Each row = {pdb, ligand_code, ligand_id, chains, smiles, [seq_hash,
    has_contacts, n_hbond, n_hydrophobic, cath]}. ``seq_hash`` groups identical
    protein sequences across different PDB IDs (dedup + leakage control).
    """
    codes = steroid_codes(ccd_smiles_path)
    biounit = _load("biounit_ligand_map.json")
    inter = _load("interactions_map.json") if attach else {}
    cath = _load("cath_domains.json") if attach else {}
    seq_keys = {}
    if attach:
        from tfsensor.ml.data.protein_seq import load_sequence_keys
        seq_keys = load_sequence_keys()

    rows = []
    for pdb, ligs in biounit.items():
        for full_id, chains in ligs.items():
            code = full_id.split(":")[0]
            if code not in codes:
                continue
            row = {
                "pdb": pdb,
                "ligand_code": code,
                "ligand_id": full_id,
                "chains": ";".join(chains),
                "smiles": codes[code],
            }
            if attach:
                ci = inter.get(pdb, {}).get(full_id)
                row["seq_hash"] = seq_keys.get(pdb, "")
                row["has_contacts"] = int(ci is not None)
                row["n_hbond"] = len(ci["hbond"]) if ci else 0
                row["n_hydrophobic"] = len(ci["hydrophobic"]) if ci else 0
                fams = sorted({c for ch in cath.get(pdb, {}).values() for c in ch})
                row["cath"] = ";".join(fams)
            rows.append(row)
    return rows, codes


def write_csv(rows, out_path):
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    cols = ["pdb", "ligand_code", "ligand_id", "chains", "smiles", "seq_hash",
            "has_contacts", "n_hbond", "n_hydrophobic", "cath"]
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ccd-smiles", default="data/ml/cache/ccd_smiles.json")
    ap.add_argument("--out", default="data/ml/lcseed_steroid_complexes.csv")
    ap.add_argument("--no-attach", action="store_true",
                    help="skip interactions/CATH joins (codes + complexes only)")
    args = ap.parse_args()

    rows, codes = mine_steroid_complexes(args.ccd_smiles, attach=not args.no_attach)
    write_csv(rows, args.out)

    pdbs = {r["pdb"] for r in rows}
    with_contacts = sum(r.get("has_contacts", 0) for r in rows)
    print(f"{len(codes)} steroid ligand codes; "
          f"{len(rows)} steroid complexes across {len(pdbs)} PDBs "
          f"({with_contacts} instances with pre-computed contacts) -> {args.out}")
    # top codes by complex count
    from collections import Counter
    top = Counter(r["ligand_code"] for r in rows).most_common(12)
    print("top steroid codes:", ", ".join(f"{c}={n}" for c, n in top))


if __name__ == "__main__":
    _main()
