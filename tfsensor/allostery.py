"""Stage 2/5 allostery: DBD-separation switch + trigger-residue mapping.

The AcrR allosteric readout (TetR-family derepression) is the mean Cα distance
between chains A and B at the HTH/DBD anchor residues 37 and 40 — small in the
DNA-bound (apo, closed) state, larger in the ligand-bound (holo, open) state.
We reuse LC-SEED's ``calculate_multi_anchor_distance`` for that exact metric.

Trigger mapping (Stage 2): a "trigger" pocket residue both (a) contacts the
ligand and (b) is spatially coupled to the 37/40 anchors (short Cα path from the
pocket toward the HTH). We score coupling as the min Cα distance from each pocket
residue to either anchor; residues that contact the ligand AND sit close to the
anchors are the allosteric levers (kept fixed during design, per the plan).

CLI:
    python -m tfsensor.allostery dbd --pdb <pose.pdb>
    python -m tfsensor.allostery trigger --holo <holo_pose.pdb> \
        --apo data/AcrR_protein_only.pdb --pocket data/pocket_residues.json \
        --out_json results/stage2_trigger/trigger_residues.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.expanduser("~/LC-Seed"))
from lcseed.iterative_design.iterative_worker import calculate_multi_anchor_distance

ANCHORS = (37, 40)


def _ca_coords(pdb_path):
    """{(chain,resSeq): (x,y,z)} for CA atoms."""
    ca = {}
    for l in open(pdb_path):
        if l.startswith("ATOM") and l[12:16].strip() == "CA":
            try:
                ca[(l[21], int(l[22:26]))] = (
                    float(l[30:38]), float(l[38:46]), float(l[46:54]))
            except ValueError:
                continue
    return ca


def dbd_distance(pdb_path, anchors=ANCHORS):
    return calculate_multi_anchor_distance(pdb_path, anchor_res_nums=anchors)


def couple_pocket_to_anchors(pdb_path, pocket_resnums, anchors=ANCHORS):
    """For each pocket residue, min Cα distance to any anchor in the same chain."""
    ca = _ca_coords(pdb_path)
    coupling = {}
    for (ch, rn), xyz in ca.items():
        if rn in pocket_resnums:
            ds = [math.dist(xyz, ca[(ch, a)]) for a in anchors if (ch, a) in ca]
            if ds:
                coupling[f"{ch}{rn}"] = round(min(ds), 2)
    return coupling


def cmd_dbd(args):
    print(json.dumps({"pdb": args.pdb,
                      "dbd_distance_37_40": round(dbd_distance(args.pdb), 3)}, indent=2))


def cmd_trigger(args):
    pocket = {h["resSeq"] for h in json.load(open(args.pocket))}
    apo_d = dbd_distance(args.apo)
    holo_d = dbd_distance(args.holo)
    coupling = couple_pocket_to_anchors(args.holo, pocket)
    # rank pocket residues by proximity to the anchors (smaller = stronger lever)
    ranked = sorted(coupling.items(), key=lambda kv: kv[1])
    # redesign spec = all pocket positions; flag the top couplers as candidate triggers
    n_trigger = args.n_trigger
    triggers = [k for k, _ in ranked[:n_trigger]]
    design_positions = sorted(coupling.keys())
    out = {
        "anchors": list(ANCHORS),
        "apo_dbd_distance": round(apo_d, 3),
        "holo_dbd_distance": round(holo_d, 3),
        "holo_minus_apo": round(holo_d - apo_d, 3),
        "pocket_residues": design_positions,
        "anchor_coupling_min_ca_dist": dict(ranked),
        "candidate_trigger_residues": triggers,
        "redesign_spec": " ".join(design_positions),
    }
    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    json.dump(out, open(args.out_json, "w"), indent=2)
    print(json.dumps(out, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dbd"); d.add_argument("--pdb", required=True)
    d.set_defaults(func=cmd_dbd)
    t = sub.add_parser("trigger")
    t.add_argument("--holo", required=True)
    t.add_argument("--apo", required=True)
    t.add_argument("--pocket", required=True)
    t.add_argument("--n_trigger", type=int, default=4)
    t.add_argument("--out_json", required=True)
    t.set_defaults(func=cmd_trigger)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
