"""Stage-3 Tier-1.5: absolute-geometry allosteric gate (the 34 Å rule).

For the Tier-1 top designs, fold the matched mutant APO and the mutant+ESTRADIOL HOLO
with Boltz-2, then apply the LAB_MANUAL absolute geometric gates on the 37/40 DBD distance:
  * Basal-stability:  Apo DBD  <  APO_MAX (default 35.5 Å)  -> not constitutively leaky
  * Agonist:          Holo DBD >  HOLO_MIN (default 38.0 Å) -> strong DNA release
  * Not-dead-binder:  Holo - Apo > 0
A design must pass all three (for estradiol) to survive to Tier-2 FEP.

  build : python -m tfsensor.design_gate build --screen <screen.json> --top 20 \
              --out_dir results/stage3_gate/inputs
  (then run Boltz on each design's inputs — see drive_stage3.sh)
  gate  : python -m tfsensor.design_gate gate --screen <screen.json> --top 20 \
              --boltz_root results/stage3_gate --seeds 1,42 --out_json results/stage3_gate/gate.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics

from tfsensor.boltz_holo_inputs import _read_first_chain, _apply_mutations
from tfsensor.allostery import dbd_distance

APO_MAX = 35.5
HOLO_MIN = 38.0
ESTRADIOL_SMILES = "C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc43)[C@@H]1CC[C@@H]2O"


def _muts_to_boltz(mutations):
    """['I61L','R123E'] -> ['61:L','123:E'] for _apply_mutations."""
    return [f"{m[1:-1]}:{m[-1]}" for m in mutations]


def _write_yaml(path, seq, ligand_smiles=None, chains=("A", "B"), n_ligand=1):
    """Two-state input. n_ligand=2 places one steroid per protomer (the biologically
    correct homodimer holo); ligand ids are single-char (L,M,...) not in `chains`."""
    lines = ["version: 1", "sequences:"]
    for ch in chains:
        lines += ["  - protein:", f"      id: {ch}", f"      sequence: {seq}"]
    if ligand_smiles:
        pool = [c for c in "LMNOPQRSTUVWXYZ" if c not in chains]
        for lid in pool[:max(1, n_ligand)]:
            lines += ["  - ligand:", f"      id: {lid}", f"      smiles: '{ligand_smiles}'"]
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def _ligand_smiles(name):
    import csv
    for r in csv.DictReader(open("data/steroid_panel.csv")):
        if r["name"] == name:
            return r["smiles"]
    raise ValueError(f"ligand {name} not in panel")


def cmd_build(args):
    scr = json.load(open(args.screen))
    designs = scr["ranked"] if getattr(args, "all", False) else scr["top"][:args.top]
    wt = _read_first_chain("data/AcrR_dimer.fasta")
    smi = _ligand_smiles(args.ligand)
    nlig = getattr(args, "n_ligand", 1)
    os.makedirs(args.out_dir, exist_ok=True)
    for d in designs:
        seq = _apply_mutations(wt, _muts_to_boltz(d["mutations"]))
        did = d["id"]
        sub = os.path.join(args.out_dir, did)
        os.makedirs(sub, exist_ok=True)
        _write_yaml(os.path.join(sub, f"{did}_apo.yaml"), seq)
        _write_yaml(os.path.join(sub, f"{did}_{args.ligand}.yaml"), seq, smi, n_ligand=nlig)
    print(f"[gate] wrote apo+{args.ligand}-holo ({nlig} ligand) inputs for "
          f"{len(designs)} designs -> {args.out_dir}")


def _mean_dbd(boltz_root, did, job, seeds):
    vals = []
    for s in seeds:
        # Boltz names the output dir after the INPUTS dir basename (= design id here),
        # i.e. boltz_results_<did>, not boltz_results_inputs.
        patt = os.path.join(boltz_root, did, f"seed{s}", f"boltz_results_{did}",
                            "predictions", job, f"{job}_model_*.pdb")
        for m in glob.glob(patt):
            vals.append(dbd_distance(m))
    return round(statistics.mean(vals), 3) if vals else None


def cmd_gate(args):
    scr = json.load(open(args.screen))
    top = scr["ranked"] if getattr(args, "all", False) else scr["top"][:args.top]
    seeds = [s.strip() for s in args.seeds.split(",") if s.strip()]
    rows = []
    for d in top:
        did = d["id"]
        apo = _mean_dbd(args.boltz_root, did, f"{did}_apo", seeds)
        holo = _mean_dbd(args.boltz_root, did, f"{did}_{args.ligand}", seeds)
        if apo is None or holo is None:
            rows.append({"id": did, "apo": apo, "holo": holo, "pass": None,
                         "note": "missing predictions"})
            continue
        delta = round(holo - apo, 3)
        c1 = apo < APO_MAX
        c2 = holo > HOLO_MIN
        c3 = delta > 0
        rows.append({"id": did, "apo_dbd": apo, "holo_dbd": holo, "delta": delta,
                     "basal_ok": c1, "agonist_ok": c2, "not_dead_ok": c3,
                     "pass": bool(c1 and c2 and c3),
                     "margin": d.get("margin_vs_rival", d.get("margin_vs_best_decoy"))})
    survivors = [r for r in rows if r.get("pass")]
    out = {"apo_max": APO_MAX, "holo_min": HOLO_MIN, "rows": rows,
           "n_survivors": len(survivors), "survivors": [r["id"] for r in survivors]}
    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    json.dump(out, open(args.out_json, "w"), indent=2)
    print(f"==== TIER-1.5 ALLOSTERIC GATE (apo<{APO_MAX}, holo>{HOLO_MIN}, delta>0) ====")
    print(f"{'id':9s} {'apo':>6s} {'holo':>6s} {'delta':>6s}  basal agon dead  PASS")
    for r in rows:
        if r.get("apo_dbd") is None:
            print(f"{r['id']:9s}  (missing predictions)"); continue
        print(f"{r['id']:9s} {r['apo_dbd']:6.2f} {r['holo_dbd']:6.2f} {r['delta']:6.2f}"
              f"   {str(r['basal_ok'])[0]}    {str(r['agonist_ok'])[0]}    "
              f"{str(r['not_dead_ok'])[0]}    {'YES' if r['pass'] else 'no'}")
    print(f"\n[gate] {len(survivors)}/{len(rows)} designs pass -> {args.out_json}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--screen", required=True); b.add_argument("--top", type=int, default=20)
    b.add_argument("--ligand", default="estradiol", help="target ligand to fold as holo")
    b.add_argument("--all", action="store_true", help="fold ALL ranked designs, not just --top")
    b.add_argument("--n_ligand", type=int, default=1, help="ligands in holo (2 = homodimer-correct)")
    b.add_argument("--out_dir", required=True); b.set_defaults(func=cmd_build)
    g = sub.add_parser("gate")
    g.add_argument("--screen", required=True); g.add_argument("--top", type=int, default=20)
    g.add_argument("--ligand", default="estradiol")
    g.add_argument("--boltz_root", required=True); g.add_argument("--seeds", default="1,42")
    g.add_argument("--all", action="store_true", help="score ALL ranked designs")
    g.add_argument("--out_json", required=True); g.set_defaults(func=cmd_gate)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
