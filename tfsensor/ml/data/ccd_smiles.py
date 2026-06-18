"""Extract PDB-code -> SMILES from the RCSB Chemical Component Dictionary.

The CCD (``components.cif.gz``, ~116 MB) is the authoritative source mapping every
PDB 3-letter ligand code to its chemistry. We parse it once with gemmi and cache a
small ``{code: smiles}`` JSON, which the steroid miner then filters with our own
:func:`tfsensor.ml.data.steroid_filter.is_steroid` (keeping the steroid definition
consistent across the whole pipeline rather than relying on RCSB's matcher).

Prefers the canonical SMILES descriptor, falling back to any SMILES.

Run in an env with gemmi (e.g. ~/LC-Seed/envs/boltz2/.venv):
    ~/LC-Seed/envs/boltz2/.venv/bin/python -m tfsensor.ml.data.ccd_smiles \
        --ccd data/ml/cache/components.cif.gz --out data/ml/cache/ccd_smiles.json
"""
from __future__ import annotations

import argparse
import json
import os

import gemmi

# descriptor "type" values, in preference order
_SMILES_TYPES = ("SMILES_CANONICAL", "SMILES")


def parse_ccd_smiles(ccd_path):
    """Return {pdb_code: smiles} parsed from a CCD mmCIF (.cif or .cif.gz)."""
    doc = gemmi.cif.read(ccd_path)  # transparently handles .gz
    out = {}
    for block in doc:
        code = block.name
        table = block.find("_pdbx_chem_comp_descriptor.", ["type", "descriptor"])
        best, best_rank = None, len(_SMILES_TYPES)
        for row in table:
            typ = gemmi.cif.as_string(row[0])
            if typ in _SMILES_TYPES:
                rank = _SMILES_TYPES.index(typ)
                if rank < best_rank:
                    best, best_rank = gemmi.cif.as_string(row[1]), rank
        if best:
            out[code] = best
    return out


def _main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ccd", default="data/ml/cache/components.cif.gz")
    ap.add_argument("--out", default="data/ml/cache/ccd_smiles.json")
    args = ap.parse_args()
    smiles = parse_ccd_smiles(args.ccd)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(smiles, open(args.out, "w"))
    print(f"parsed {len(smiles)} code->SMILES -> {args.out}")
    for c in ("STR", "EST", "TES", "DHT", "HCY", "DEX"):
        print(f"  {c}: {smiles.get(c)}")


if __name__ == "__main__":
    _main()
