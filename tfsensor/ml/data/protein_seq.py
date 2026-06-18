"""Protein-sequence identity keys — defeat PDB redundancy & sequence leakage.

The same protein is deposited under many PDB IDs (e.g. one steroid receptor
solved dozens of times with different ligands). Counting those as independent
datapoints inflates the dataset, and — worse — letting the *same sequence* fall
into different train/val/test splits leaks (LP-PDBBind controls exactly this).

We assign each PDB a ``seq_hash`` = md5 of its sorted distinct protein-entity
sequences (from LC-SEED ``protein_annotation.json``). Identical-sequence entries
(any number of PDB IDs) collapse to one key, so they dedup and stay in one split.

NOTE: this is *exact*-sequence grouping — the precise fix for "different id, same
sequence". Near-identical sequences (≥95% id, incl. single-point mutants) are NOT
merged here; cluster with MMseqs2 for that rigour (planned upgrade). Keeping
point-mutants distinct is actually desirable for the AcrR preference task.
"""
from __future__ import annotations

import hashlib
import json
import os

from tfsensor import config

ANNOTATION = os.path.join(config.LC_SEED, "static/dataset/protein_annotation.json")


def _seq_hash(sequences):
    if not sequences:
        return ""
    joined = "|".join(sorted(set(sequences)))
    return "seq:" + hashlib.md5(joined.encode()).hexdigest()[:12]


def load_sequence_keys(annotation_path=ANNOTATION):
    """Return {pdb: seq_hash} for every annotated PDB (one big load)."""
    pa = json.load(open(annotation_path))
    keys = {}
    for pdb, ann in pa.items():
        seqs = [e["sequence"] for e in ann.get("entities", []) if e.get("sequence")]
        keys[pdb] = _seq_hash(seqs)
    return keys


def redundancy_report(seq_keys, pdbs=None):
    """Summarise PDB→sequence redundancy over an optional subset of PDBs."""
    from collections import Counter
    pdbs = pdbs or list(seq_keys)
    present = [seq_keys[p] for p in pdbs if seq_keys.get(p)]
    c = Counter(present)
    return {"n_pdbs": len(present), "n_unique_sequences": len(c),
            "largest_cluster": max(c.values()) if c else 0}
