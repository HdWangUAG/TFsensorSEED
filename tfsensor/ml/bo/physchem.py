"""Transferable physicochemical features for a (multi-)mutation.

Encodes a mutation list as distance-weighted chemical-property DELTAS — NOT
position identity — so the feature transfers across positions and a
leave-one-position-out benchmark is honest (a held-out position is scored from
chemistry + ligand-distance learned at other positions, not memorized).

Per mutation (wt→aa at model position p): property deltas {hydrophobicity, volume,
charge, H-bond donors, H-bond acceptors} and a proximity weight w = 1/(1+d) where
d = min-distance of residue p to the bound steroid (from the holo PDB). A multi-
mutant feature is the additive sum over its mutations + a few aggregates.

Pure-numpy / stdlib (reuses the dependency-free PDB parser).
"""
from __future__ import annotations

import math
import os

import numpy as np

from tfsensor import config
from tfsensor.prep_receptor import parse_pdb, pocket_scan

HOLO_PDB = os.path.join(config.REPO_ROOT, "data/AcrR_STR_001.pdb")
LIG_RESN = "STR"

# Kyte–Doolittle hydrophobicity, residue volume (Å³), formal charge @pH7,
# sidechain H-bond donors, H-bond acceptors (approximate, sufficient as features).
_KD = {"A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5, "E": -3.5,
       "G": -0.4, "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8,
       "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2}
_VOL = {"A": 88.6, "R": 173.4, "N": 114.1, "D": 111.1, "C": 108.5, "Q": 143.8,
        "E": 138.4, "G": 60.1, "H": 153.2, "I": 166.7, "L": 166.7, "K": 168.6,
        "M": 162.9, "F": 189.9, "P": 112.7, "S": 89.0, "T": 116.1, "W": 227.8,
        "Y": 193.6, "V": 140.0}
_CHG = {"D": -1.0, "E": -1.0, "K": 1.0, "R": 1.0, "H": 0.1}
_HBD = {"R": 3, "K": 1, "W": 1, "N": 1, "Q": 1, "H": 1, "S": 1, "T": 1, "Y": 1}
_HBA = {"D": 2, "E": 2, "N": 1, "Q": 1, "H": 1, "S": 1, "T": 1, "Y": 1}


def _props(aa):
    return np.array([_KD.get(aa, 0.0), _VOL.get(aa, 0.0), _CHG.get(aa, 0.0),
                     float(_HBD.get(aa, 0)), float(_HBA.get(aa, 0))])


_DIST_CACHE = {}


def ligand_distances(holo_pdb=HOLO_PDB, lig_resn=LIG_RESN):
    """{model_resSeq: min-distance to the bound ligand (Å)} from the holo PDB."""
    if holo_pdb in _DIST_CACHE:
        return _DIST_CACHE[holo_pdb]
    chains, ligand_atoms = parse_pdb(holo_pdb)
    lig = [a for a in ligand_atoms if a[1] == lig_resn] or ligand_atoms
    hits = pocket_scan(chains, lig, cutoff=10_000.0)  # all residues + min_dist
    d = {}
    for h in hits:
        p, md = h["resSeq"], h["min_dist"]
        if p not in d or md < d[p]:
            d[p] = md
    _DIST_CACHE[holo_pdb] = d
    return d


# feature names (for interpretability / ablation reporting)
FEATURE_NAMES = (
    [f"w*Δ{p}" for p in ("hyd", "vol", "chg", "hbd", "hba")] +
    [f"Δ{p}" for p in ("hyd", "vol", "chg", "hbd", "hba")] +
    ["n_mut", "min_dist", "sum_w"])


def featurize(mutations, dists=None):
    """Mutation list [(wt,pos,aa), ...] -> fixed 13-dim transferable feature vector."""
    dists = dists if dists is not None else ligand_distances()
    wsum = np.zeros(5)   # distance-weighted property deltas
    rsum = np.zeros(5)   # raw property deltas
    ws, mind = [], math.inf
    for wt, pos, aa in mutations:
        d = dists.get(pos, 15.0)          # unknown/far position → 15 Å
        w = 1.0 / (1.0 + d)
        delta = _props(aa) - _props(wt)
        wsum += w * delta
        rsum += delta
        ws.append(w)
        mind = min(mind, d)
    n = len(mutations)
    return np.concatenate([wsum, rsum,
                           [float(n), (mind if n else 0.0), float(sum(ws))]])


def featurize_many(mutation_lists):
    dists = ligand_distances()
    return np.vstack([featurize(m, dists) for m in mutation_lists])
