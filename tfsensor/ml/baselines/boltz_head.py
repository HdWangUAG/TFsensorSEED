"""Boltz-2 affinity head — NEGATIVE CONTROL ONLY.

Strategic decision: AF3-like co-folding models (Boltz-2, Protenix, Chai) are
notoriously insensitive to single point mutations, so Boltz-2 is **not** a
candidate primary scorer here. Its sole role is to generate negative-control
evidence: run it on WT vs a point-mutant pocket and show the binder-likelihood
(`affinity_probability_binary`) barely shifts — i.e. it fails to capture the
point-mutation-driven preference shifts that flex-ddG/FEP and the wet-lab scan do.

Parsing reuses the in-repo `tfsensor.boltz_selectivity` (no new model code). The
actual Boltz inference is GPU-heavy and is left as an explicit, deferred step
(`run_*` below shells to `config.BOLTZ_BIN`); the parsing path is import-safe and
unit-testable without a GPU.
"""
from __future__ import annotations

import json
import os

from tfsensor import config
from tfsensor.ml.baselines.base import Scorer

# higher affinity_probability_binary = Boltz thinks "more likely a binder"
PRIMARY_METRIC = "affinity_probability_binary"


def binder_prob_from_affinity_json(affinity_json):
    """Read Boltz's affinity_probability_binary from one affinity_<name>.json."""
    d = json.load(open(affinity_json))
    return d.get(PRIMARY_METRIC)


class BoltzNegativeControl(Scorer):
    """Reads Boltz-2 predictions as a negative control (does not run Boltz)."""

    name = "boltz2_negctl"
    is_negative_control = True

    def __init__(self, pocket_json=None):
        self.pocket_json = pocket_json or os.path.join(
            config.REPO_ROOT, "data/pocket_residues.json")

    def read_pocket_panel(self, pred_parents):
        """Parse existing Boltz prediction dirs into {ligand: binder_prob}.

        pred_parents: list of Boltz output parent dirs (as produced by the
        existing pipeline). Reuses boltz_selectivity.collect/build_profile.
        """
        from tfsensor.boltz_selectivity import (load_pocket, collect,
                                                 build_profile, load_panel_names)
        pocket = load_pocket(self.pocket_json)
        panel = load_panel_names(os.path.join(config.REPO_ROOT,
                                              "data/steroid_panel.csv"))
        records = collect(pred_parents, pocket)
        bp, _ = build_profile(records, panel)
        return bp

    def score(self, receptor_pdb, ligand_sdf, autobox_ligand=None, workdir=None):
        raise NotImplementedError(
            "Boltz-2 is a negative control: use read_pocket_panel() on existing "
            "Boltz predictions, or run_for_variant() to generate them (GPU).")

    # --- deferred GPU step (documented, not auto-fired) --------------------
    def run_for_variant(self, *args, **kwargs):
        raise NotImplementedError(
            "Deferred GPU step. Generate WT and mutant holo inputs via "
            "tfsensor.boltz_holo_inputs, run `config.BOLTZ_BIN`, then parse with "
            "read_pocket_panel(). Left manual because Boltz inference is expensive "
            "and this is only a negative control.")


def preference_shift_from_binder_probs(bp_wt, bp_mut, lig_a, lig_b):
    """Negative-control preference shift from Boltz binder probabilities.

    Returns the mutation's predicted favored ligand between A and B, using the
    change in binder_prob (Δ on mutation). If Boltz is mutation-insensitive these
    deltas are ~0 and the 'favored' call is unstable — which is the point.
    """
    if any(bp is None for bp in (bp_wt.get(lig_a), bp_wt.get(lig_b),
                                 bp_mut.get(lig_a), bp_mut.get(lig_b))):
        return None
    shift_a = bp_mut[lig_a] - bp_wt[lig_a]
    shift_b = bp_mut[lig_b] - bp_wt[lig_b]
    favored = lig_a if shift_a > shift_b else lig_b
    return {"favored": favored, "delta_a": shift_a, "delta_b": shift_b,
            "magnitude": abs(shift_a - shift_b)}
