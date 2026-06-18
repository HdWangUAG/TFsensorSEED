"""Tests for sequence-aware dedup + grouping in build_dataset.from_lcseed.

Guards the fix for "same protein sequence under different PDB IDs": such rows
must dedup to one representative and share a split group_key.

Run:
    PYTHONPATH=. ~/LC-Seed/envs/app/.venv/bin/python tfsensor/ml/tests/test_dataset_dedup.py
"""
from __future__ import annotations

import csv
import os
import tempfile

from tfsensor.ml.data.build_dataset import from_lcseed

# testosterone SMILES (valid; murcko_scaffold must not choke)
TES = "C[C@]12CC[C@H]3[C@@H](CCC4=CC(=O)CC[C@]34C)[C@@H]1CC[C@@H]2O"
EST = "C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc43)[C@@H]1CC[C@@H]2O"


def _write_csv(rows):
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    cols = ["pdb", "ligand_code", "ligand_id", "chains", "smiles", "seq_hash",
            "has_contacts", "n_hbond", "n_hydrophobic", "cath"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return path


def test_dedup_same_sequence_same_ligand():
    # same protein sequence (seqX) + same ligand (TES) under 3 different PDBs
    rows = [
        {"pdb": "1aaa", "ligand_code": "TES", "ligand_id": "TES:A:1", "chains": "A",
         "smiles": TES, "seq_hash": "seq:X", "has_contacts": 0, "n_hbond": 0,
         "n_hydrophobic": 0, "cath": "1.10.10.10"},
        {"pdb": "2bbb", "ligand_code": "TES", "ligand_id": "TES:A:1", "chains": "A",
         "smiles": TES, "seq_hash": "seq:X", "has_contacts": 1, "n_hbond": 2,
         "n_hydrophobic": 3, "cath": "1.10.10.10"},
        {"pdb": "3ccc", "ligand_code": "TES", "ligand_id": "TES:A:1", "chains": "A",
         "smiles": TES, "seq_hash": "seq:X", "has_contacts": 0, "n_hbond": 0,
         "n_hydrophobic": 0, "cath": "1.10.10.10"},
    ]
    out = from_lcseed(_write_csv(rows), dedup=True)
    assert len(out) == 1, "identical (sequence, ligand) must collapse to one row"
    assert out[0]["has_contacts"] == 1, "representative should be the one with contacts"
    assert out[0]["group_key"] == "seq:X", "group_key must be the sequence hash"


def test_same_sequence_different_ligand_kept_separate():
    rows = [
        {"pdb": "1aaa", "ligand_code": "TES", "ligand_id": "TES:A:1", "chains": "A",
         "smiles": TES, "seq_hash": "seq:X", "has_contacts": 1, "n_hbond": 0,
         "n_hydrophobic": 0, "cath": ""},
        {"pdb": "1aaa", "ligand_code": "EST", "ligand_id": "EST:A:2", "chains": "A",
         "smiles": EST, "seq_hash": "seq:X", "has_contacts": 1, "n_hbond": 0,
         "n_hydrophobic": 0, "cath": ""},
    ]
    out = from_lcseed(_write_csv(rows), dedup=True)
    assert len(out) == 2, "same protein, different ligands = two datapoints"
    # but both share the split group (same sequence) -> no cross-split leakage
    assert {r["group_key"] for r in out} == {"seq:X"}


if __name__ == "__main__":
    test_dedup_same_sequence_same_ligand()
    test_same_sequence_different_ligand_kept_separate()
    print("OK: all dataset dedup/grouping tests passed")
