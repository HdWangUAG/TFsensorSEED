"""Common interface for pretrained protein-ligand scorers.

Each baseline (gnina, GEMS, the Boltz-2 affinity head, ...) implements ``Scorer``
so the Phase-1 harness can drive them uniformly and tabulate the same metrics
(plan: Phase 1). A score dict uses these optional keys (NaN/absent if a model
doesn't produce one):

    affinity_pK     higher = stronger binder (gnina CNNaffinity, pKd-like)
    dG_kcalmol      more negative = stronger
    binder_prob     P(binder) in [0,1]
    pose_score      pose-quality / confidence (gnina CNNscore, etc.)
    raw             model-specific extras
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod


class Scorer(ABC):
    name = "scorer"

    @abstractmethod
    def score(self, receptor_pdb, ligand_sdf, autobox_ligand=None, workdir=None):
        """Return a score dict (see module docstring) for one complex."""
        raise NotImplementedError


def extract_hetatm_ligand(holo_pdb, resname, out_pdb):
    """Write the HETATM atoms of one ligand to a small PDB (e.g. autobox ref).

    Coordinates are all that downstream autoboxing needs; bonds are perceived
    by OpenBabel from distance, so CONECT records are unnecessary.
    """
    os.makedirs(os.path.dirname(os.path.abspath(out_pdb)) or ".", exist_ok=True)
    n = 0
    with open(out_pdb, "w") as out:
        for line in open(holo_pdb):
            if line.startswith("HETATM") and line[17:20].strip() == resname:
                out.write(line)
                n += 1
        out.write("END\n")
    if n == 0:
        raise ValueError(f"no HETATM {resname!r} found in {holo_pdb}")
    return out_pdb
