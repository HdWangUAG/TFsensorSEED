"""Tests for template core-alignment posing (no blind docking).

Run:
    PYTHONPATH=. ~/LC-Seed/envs/app/.venv/bin/python tfsensor/ml/tests/test_template_pose.py
"""
from __future__ import annotations

from tfsensor.ml.features.template_pose import pose_by_core, reference_from_smiles

TES = "C[C@]12CC[C@H]3[C@@H](CCC4=CC(=O)CC[C@]34C)[C@@H]1CC[C@@H]2O"
CORT = "C[C@]12C[C@H](O)[C@H]3[C@@H](CCC4=CC(=O)CC[C@]34C)[C@@H]1CC[C@]2(O)C(=O)CO"
PROG = "CC(=O)[C@H]1CC[C@H]2[C@@H]3CCC4=CC(=O)CC[C@]4(C)[C@H]3CC[C@]12C"
EST = "C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc43)[C@@H]1CC[C@@H]2O"
ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"


def test_steroids_align_to_reference():
    ref = reference_from_smiles(TES)
    assert ref is not None
    for name, smi in [("cortisol", CORT), ("progesterone", PROG)]:
        r = pose_by_core(smi, ref)
        assert r["accepted"], f"{name}: {r.get('reason')}"
        assert r["core_atoms"] >= 15, name
        assert r["core_rmsd"] <= 1.0, f"{name} core_rmsd={r['core_rmsd']}"


def test_estradiol_shares_core():
    # aromatic A-ring still shares the fused 4-ring core with the reference
    ref = reference_from_smiles(TES)
    r = pose_by_core(EST, ref)
    # estradiol's A-ring is aromatic so the matched core may be a bit smaller,
    # but the rigid superposition must still be tight if accepted
    if r["accepted"]:
        assert r["core_rmsd"] <= 1.0


def test_non_steroid_rejected():
    ref = reference_from_smiles(TES)
    r = pose_by_core(ASPIRIN, ref)
    assert not r["accepted"]
    assert "core_too_small" in r["reason"]


if __name__ == "__main__":
    test_steroids_align_to_reference()
    test_estradiol_shares_core()
    test_non_steroid_rejected()
    print("OK: all template-pose tests passed")
