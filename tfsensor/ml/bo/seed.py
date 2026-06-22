"""Seed objectives from the empirical single-mutant GFP scan.

Parses `results/stage1f_empirical/scan_model_numbering.csv` (84 single mutants +
WT × 19 ligands, GFP fold-induction) and turns it into a per-variant objective for
a chosen target steroid. This is round-0 of the DBTL loop and the corpus for the
P1 grouped-CV kill-switch.

Objective (selectivity, maximized):
    y1 = log10( max(target_fold, EPS) / max(max_offtarget_fold, EPS) )
Single-dose is used ONLY for seeding + the retrospective benchmark; the panel
flagged single-dose as misranking, so the *trusted* objective from round-1 on is
dose-response (handled later). EPS floors no-induction/noise (≤1) to 1.

Pure-numpy / stdlib — importable in any env.
"""
from __future__ import annotations

import csv
import math
import os
import re

from tfsensor import config

SCAN_CSV = os.path.join(config.REPO_ROOT,
                        "results/stage1f_empirical/scan_model_numbering.csv")
EPS = 1.0
# the four primary panel steroids; the rest are decoys/off-targets by default
PRIMARY = ["testosterone", "progesterone", "estradiol", "cortisol"]
_MUT_RE = re.compile(r"^([A-Z])(\d+)([A-Z])$")


def parse_mutation(token):
    """'Q101R' -> ('Q', 101, 'R'); 'WT' -> None. Raises on a malformed token."""
    token = token.strip()
    if token.upper() == "WT":
        return None
    m = _MUT_RE.match(token)
    if not m:
        raise ValueError(f"unparseable mutation {token!r}")
    return (m.group(1), int(m.group(2)), m.group(3))


def load_scan(csv_path=SCAN_CSV):
    """Return {model_mut: {ligand: fold(float)}} keyed by the model-numbering mutation."""
    rows = {}
    with open(csv_path) as fh:
        reader = csv.reader(fh)
        header = [h.strip() for h in next(reader)]
        ligands = [h for h in header if h not in ("exp_mut", "model_mut", "TOP")]
        idx = {h: i for i, h in enumerate(header)}
        for raw in reader:
            if not raw or len(raw) < len(header):
                continue
            key = raw[idx["model_mut"]].strip()
            vals = {}
            for lig in ligands:
                try:
                    vals[lig] = float(raw[idx[lig]].strip())
                except (ValueError, IndexError):
                    vals[lig] = float("nan")
            rows[key] = vals
    return rows, ligands


def selectivity(folds, target, offtargets, eps=EPS):
    """log10(target / best-offtarget), floored at eps. None if target missing."""
    ft = folds.get(target)
    if ft is None or ft != ft:  # nan
        return None
    offs = [folds.get(o, float("nan")) for o in offtargets]
    offs = [o for o in offs if o == o]  # drop nan
    f_off = max(offs) if offs else eps
    return math.log10(max(ft, eps) / max(f_off, eps))


def objective_table(target, offtargets=None, csv_path=SCAN_CSV, eps=EPS,
                    include_wt=True):
    """Return (variants, mutations, y) for the chosen target.

    variants: list of model_mut strings (excl. WT unless include_wt)
    mutations: list of mutation-lists (each [(wt,pos,aa), ...]; [] for WT)
    y: list of selectivity objective floats (maximize).
    """
    rows, ligands = load_scan(csv_path)
    if offtargets is None:
        offtargets = [l for l in ligands if l != target]
    variants, mutations, y = [], [], []
    for key, folds in rows.items():
        if key == "WT" and not include_wt:
            continue
        s = selectivity(folds, target, offtargets, eps)
        if s is None:
            continue
        mut = [] if key == "WT" else [parse_mutation(key)]
        variants.append(key)
        mutations.append(mut)
        y.append(s)
    return variants, mutations, y


# known wet-lab leads per target — the P1 benchmark must rank these high
KNOWN_LEADS = {
    "testosterone": ["E106L", "L85I", "I61L"],
    "cortisol": ["R123E"],
}
