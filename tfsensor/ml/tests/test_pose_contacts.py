"""Integration test for the pose→contact bridge (skips if references absent).

Run (after `python -m tfsensor.ml.data.reference_structures --build-all`):
    PYTHONPATH=. ~/LC-Seed/envs/app/.venv/bin/python tfsensor/ml/tests/test_pose_contacts.py
"""
from __future__ import annotations

import os

TES = "C[C@]12CC[C@H]3[C@@H](CCC4=CC(=O)CC[C@]34C)[C@@H]1CC[C@@H]2O"


def test_testosterone_on_AR_recovers_anchor_contacts():
    from tfsensor.ml.features.pose_contacts import load_references, featurize_ligand
    sel = "data/ml/refs/reference_selection.json"
    if not os.path.exists(sel):
        print("(refs absent — skipping integration test)")
        return
    refs = load_references(sel)
    if "AR" not in refs:
        return
    ar = refs["AR"]
    r = featurize_ligand(TES, ar["ligand_sdf"], ar["ref_pdb"], ar["pocket_json"])
    assert r["accepted"], r.get("reason")
    assert r["core_rmsd"] <= 1.0
    assert r["fingerprint"].sum() > 0, "expected non-empty contact fingerprint"
    # AR anchors the A-ring 3-keto via Arg/Asn H-bonds — must show up
    contacts = r["contacts"]
    hb_res = {c.split(":")[0] for c in contacts["hbond"]}
    assert hb_res & {"ARG", "ASN", "THR", "GLN"}, f"no polar anchor in {hb_res}"


if __name__ == "__main__":
    test_testosterone_on_AR_recovers_anchor_contacts()
    print("OK: pose-contact bridge test passed")
