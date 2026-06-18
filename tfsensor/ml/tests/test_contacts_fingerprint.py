"""Tests for the interpretable interaction-fingerprint featurizer.

Run:
    PYTHONPATH=. ~/LC-Seed/envs/app/.venv/bin/python tfsensor/ml/tests/test_contacts_fingerprint.py
"""
from __future__ import annotations

from tfsensor.ml.features.contacts_fingerprint import (fingerprint_vector,
                                                       fingerprint_dict,
                                                       top_contacts,
                                                       FEATURE_NAMES)


def test_counts_and_names():
    rec = {"hydrophobic": ["PHE:219", "VAL:240", "PHE:213"],
           "hbond": ["GLU:106"], "pistacking": [], "saltbridge": []}
    d = fingerprint_dict(rec)
    assert d["PHE:hydrophobic"] == 2
    assert d["VAL:hydrophobic"] == 1
    assert d["GLU:hbond"] == 1
    assert fingerprint_vector(rec).sum() == 4


def test_empty_and_unknown():
    assert fingerprint_vector({}).sum() == 0
    assert fingerprint_vector(None).sum() == 0
    # non-standard residue -> OTHER bucket
    d = fingerprint_dict({"hbond": ["HOH:500"], "hydrophobic": [],
                          "pistacking": [], "saltbridge": []})
    assert d["OTHER:hbond"] == 1


def test_feature_space_fixed():
    assert len(FEATURE_NAMES) == 21 * 4   # 20 AA + OTHER, x 4 interaction types
    rec = {"hbond": ["ARG:123"], "hydrophobic": [], "pistacking": [], "saltbridge": []}
    assert len(fingerprint_vector(rec)) == len(FEATURE_NAMES)
    assert top_contacts(rec, k=1) == [("ARG:hbond", 1.0)]


if __name__ == "__main__":
    test_counts_and_names()
    test_empty_and_unknown()
    test_feature_space_fixed()
    print("OK: all contact-fingerprint tests passed")
