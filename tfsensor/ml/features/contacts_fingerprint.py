"""Interpretable interaction-fingerprint features (residue-type × interaction-type).

The pivot makes interpretability mandatory: a preference score must map back to
specific residue–ligand contacts. We encode each (pocket, ligand) complex as a
fixed-length vector indexed by (residue type, interaction type) — so a model's
weight/attribution on, say, ("GLU", "hbond") reads directly as "Glu H-bonds drive
this score". This is the general, protein-agnostic interpretable representation;
for a known pocket (e.g. AcrR) the same contacts also localise to specific
residues (Glu123) via the residue id in the contact record.

Input contact records follow LC-SEED's `interactions_map.json` schema:
    {"hbond": ["GLU:123", ...], "hydrophobic": [...], "pistacking": [...],
     "saltbridge": [...]}
The same featurizer applies to contacts computed for a docked pose (e.g. via
ProLIF) so affinity ligands without a crystal can be featurized identically.
"""
from __future__ import annotations

import numpy as np

AA = ["ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
      "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL"]
OTHER = "OTHER"
RESTYPES = AA + [OTHER]
ITYPES = ["hbond", "hydrophobic", "pistacking", "saltbridge"]

FEATURE_NAMES = [f"{rt}:{it}" for it in ITYPES for rt in RESTYPES]
_INDEX = {name: i for i, name in enumerate(FEATURE_NAMES)}


def _restype(residue_token):
    """'PHE:219' -> 'PHE'; map unknown/non-standard to OTHER."""
    rt = residue_token.split(":", 1)[0].strip().upper()
    return rt if rt in AA else OTHER


def fingerprint_vector(contact_rec):
    """Return a (len(FEATURE_NAMES),) float count vector for one complex."""
    vec = np.zeros(len(FEATURE_NAMES), dtype=float)
    if not contact_rec:
        return vec
    for itype in ITYPES:
        for token in contact_rec.get(itype, []) or []:
            vec[_INDEX[f"{_restype(token)}:{itype}"]] += 1.0
    return vec


def fingerprint_dict(contact_rec):
    """Same counts as a sparse {feature_name: count} dict (nonzero only)."""
    vec = fingerprint_vector(contact_rec)
    return {FEATURE_NAMES[i]: vec[i] for i in np.nonzero(vec)[0]}


def top_contacts(contact_rec, k=5):
    """Most frequent (residue-type, interaction-type) contacts — for readouts."""
    d = fingerprint_dict(contact_rec)
    return sorted(d.items(), key=lambda kv: -kv[1])[:k]


def _main():
    import argparse
    import csv
    import json
    import os
    from tfsensor import config

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true",
                    help="featurize a few real LC-SEED steroid complexes")
    args = ap.parse_args()
    if args.demo:
        im = json.load(open(os.path.join(config.LC_SEED,
                                          "static/dataset/interactions_map.json")))
        rows = [r for r in csv.DictReader(
            open("data/ml/lcseed_steroid_complexes.csv")) if r["has_contacts"] == "1"]
        shown = 0
        for r in rows:
            rec = im.get(r["pdb"], {}).get(r["ligand_id"])
            if rec and sum(len(v) for v in rec.values()) > 0:
                print(f"{r['pdb']} {r['ligand_id']} ({r['ligand_code']}): "
                      f"{top_contacts(rec)}")
                shown += 1
                if shown >= 5:
                    break


if __name__ == "__main__":
    _main()
