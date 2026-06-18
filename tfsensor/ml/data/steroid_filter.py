"""Detect the steroid (gonane) nucleus in arbitrary ligands.

Used to filter PDBbind / PDBe / BindingDB ligands down to steroids for the
binding-ML dataset. The honest lesson from the planning research: a single
hard-coded single-bond SMARTS misses unsaturated steroids (testosterone's
4-en-3-one, cholesterol's Δ5) and aromatic-A-ring estrogens (estradiol), and a
hand-written fused-ring SMARTS is brittle to author correctly. So the test
here is **RDKit ring perception**, which is bond-order- and aromaticity-
agnostic and fast enough (RingInfo is computed once; the combinatorics run
over only the handful of six-membered rings) that no separate pre-filter is
needed.

The gonane nucleus = perhydrocyclopenta[a]phenanthrene: three fused
six-membered carbocycles (rings A/B/C) + one fused five-membered carbocycle
(ring D), 6-6-6-5. Counting shared fusion atoms, the four rings span exactly
**17 carbons** (6+6+6+5 − 2·3 fusion bonds). That atom count, together with
the ring-size signature and an all-carbon constraint, is a tight, specific
fingerprint for the steroid skeleton.

Run in an rdkit env, e.g.:
    ~/LC-Seed/envs/app/.venv/bin/python -m tfsensor.ml.data.steroid_filter --smiles "<SMILES>"
    ~/LC-Seed/envs/app/.venv/bin/python -m tfsensor.ml.data.steroid_filter --panel data/steroid_panel.csv
"""
from __future__ import annotations

import argparse
import csv
from itertools import combinations

from rdkit import Chem, RDLogger

# This is a bulk filtering utility run over whole ligand dictionaries (e.g. the
# ~50k-entry CCD), many of which are exotic/organometallic and unparseable. Their
# RDKit parse warnings are expected noise here (they simply fail the steroid test),
# so silence the RDKit logger at import.
RDLogger.DisableLog("rdApp.*")

# The gonane nucleus spans exactly 17 carbons across its four fused rings.
_GONANE_NUCLEUS_ATOMS = 17
_RING_SIZES = (6, 6, 6, 5)  # rings A, B, C, D


def _all_carbon(mol, ring_atoms):
    return all(mol.GetAtomWithIdx(i).GetAtomicNum() == 6 for i in ring_atoms)


def _fused(ring_a, ring_b):
    """Two rings are fused iff they share an edge (>= 2 atoms)."""
    return len(ring_a & ring_b) >= 2


def _connected(rings):
    """Is this set of rings a single connected fused system?"""
    n = len(rings)
    seen = {0}
    stack = [0]
    while stack:
        i = stack.pop()
        for j in range(n):
            if j not in seen and _fused(rings[i], rings[j]):
                seen.add(j)
                stack.append(j)
    return len(seen) == n


def find_gonane_nucleus(mol):
    """Return the atom-index set of a gonane nucleus if present, else None.

    Searches for four mutually-fused all-carbon rings with size signature
    {6,6,6,5} whose atom union is exactly 17 carbons — the steroid skeleton.
    Returns the first such nucleus found (sorted tuple of atom indices).
    """
    if mol is None:
        return None
    ri = mol.GetRingInfo()
    rings = [set(r) for r in ri.AtomRings()]
    # carbocyclic rings only, bucketed by size
    six = [r for r in rings if len(r) == 6 and _all_carbon(mol, r)]
    five = [r for r in rings if len(r) == 5 and _all_carbon(mol, r)]
    if len(six) < 3 or not five:
        return None
    for trio in combinations(six, 3):
        for d_ring in five:
            quartet = list(trio) + [d_ring]
            union = set().union(*quartet)
            if len(union) != _GONANE_NUCLEUS_ATOMS:
                continue
            if _connected(quartet):
                return tuple(sorted(union))
    return None


def is_steroid(mol_or_smiles):
    """True if the molecule contains a gonane (steroid) nucleus.

    Accepts an RDKit Mol or a SMILES string.
    """
    mol = mol_or_smiles
    if isinstance(mol_or_smiles, str):
        mol = Chem.MolFromSmiles(mol_or_smiles)
    return find_gonane_nucleus(mol) is not None


def _main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--smiles", help="classify a single SMILES")
    ap.add_argument("--panel", help="CSV with name,smiles columns to classify")
    args = ap.parse_args()
    if args.smiles:
        m = Chem.MolFromSmiles(args.smiles)
        nucleus = find_gonane_nucleus(m)
        print(f"is_steroid={nucleus is not None}  nucleus_atoms={nucleus}")
    if args.panel:
        for row in csv.DictReader(open(args.panel)):
            name = row.get("name", "?").strip()
            smi = row["smiles"].strip()
            print(f"{name:16s} is_steroid={is_steroid(smi)}")


if __name__ == "__main__":
    _main()
