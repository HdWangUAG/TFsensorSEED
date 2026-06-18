"""Sanity tests for the gonane (steroid) nucleus detector.

Run with an rdkit env:
    ~/LC-Seed/envs/app/.venv/bin/python -m pytest tfsensor/ml/tests/test_steroid_filter.py -q
or standalone (no pytest needed):
    ~/LC-Seed/envs/app/.venv/bin/python tfsensor/ml/tests/test_steroid_filter.py
"""
from __future__ import annotations

from tfsensor.ml.data.steroid_filter import is_steroid

# The 4 AcrR panel steroids (data/steroid_panel.csv) — all must be detected,
# including aromatic-A-ring estradiol and the unsaturated 4-en-3-ones.
STEROIDS = {
    "estradiol":     "C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc43)[C@@H]1CC[C@@H]2O",
    "testosterone":  "C[C@]12CC[C@H]3[C@@H](CCC4=CC(=O)CC[C@]34C)[C@@H]1CC[C@@H]2O",
    "progesterone":  "CC(=O)[C@H]1CC[C@H]2[C@@H]3CCC4=CC(=O)CC[C@]4(C)[C@H]3CC[C@]12C",
    "cortisol":      "C[C@]12C[C@H](O)[C@H]3[C@@H](CCC4=CC(=O)CC[C@]34C)[C@@H]1CC[C@]2(O)C(=O)CO",
    # extra positives: a sterol and a bare nucleus
    "cholesterol":   "CC(C)CCC[C@@H](C)[C@H]1CC[C@H]2[C@@H]3CC=C4C[C@@H](O)CC[C@]4(C)[C@H]3CC[C@]12C",
    "dexamethasone": "C[C@@H]1C[C@H]2[C@@H]3CCC4=CC(=O)C=C[C@@]4(C)[C@@]3(F)[C@@H](O)C[C@]2(C)[C@@]1(O)C(=O)CO",
}

# Non-steroids — must all be rejected.
NON_STEROIDS = {
    "benzene":  "c1ccccc1",
    "aspirin":  "CC(=O)Oc1ccccc1C(=O)O",
    "caffeine": "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
    "glucose":  "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
    "indole":   "c1ccc2[nH]ccc2c1",
    "estrone_decoy_phenol": "Oc1ccccc1",  # lone phenol, not a steroid
}


def test_panel_steroids_detected():
    for name, smi in STEROIDS.items():
        assert is_steroid(smi), f"{name} should be detected as a steroid"


def test_non_steroids_rejected():
    for name, smi in NON_STEROIDS.items():
        assert not is_steroid(smi), f"{name} should NOT be detected as a steroid"


if __name__ == "__main__":
    test_panel_steroids_detected()
    test_non_steroids_rejected()
    print("OK: all steroid-filter sanity tests passed")
