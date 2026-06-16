"""Stage-3 Tier-2: Relative Binding Free Energy (RBFE) arbiter — scaffold + prototype.

The ultimate judge before gene synthesis. For a protein point-mutation RBFE (e.g. the
ground-truth WT↔L147R with cortisol bound), the rigorous quantity is the alchemical
thermodynamic cycle:

      WT·L  --ΔG_bound(WT→mut)-->  MUT·L
       |                              |
   ΔG_bind(WT)                   ΔG_bind(MUT)
       |                              |
      WT + L --ΔG_apo(WT→mut)--> MUT + L

   ΔΔG_bind = ΔG_bind(MUT) − ΔG_bind(WT) = ΔG_bound(WT→mut) − ΔG_apo(WT→mut)

i.e. alchemically morph the mutated sidechain (Leu→Arg) in BOTH the ligand-bound and
apo states; the difference is the rigorous ΔΔG of binding — the gold-standard check on
the flex-ddG Tier-1 ranking.

Tooling: protein-mutation RBFE is canonically done with **pmx + GROMACS** (hybrid
topology, non-equilibrium TI). This module (a) detects available engines, (b) PREPARES
the two endpoint complexes + the cycle spec from our existing Boltz holo poses, and (c)
runs the prototype IF an engine is installed, else emits a precise setup plan
(SETUP_FEP.md). Execution is gated on standing up GROMACS/pmx (or OpenFE/Amber-TI).

  check   : python -m tfsensor.fep_rbfe check
  prepare : python -m tfsensor.fep_rbfe prepare --variant l147r --ligand cortisol \
                --out_dir results/stage3_fep/proto_l147r_cortisol
"""
from __future__ import annotations

import argparse
import json
import os
import shutil

# protein-mutation RBFE prototype: a known experimental ground truth to validate setup
GROUND_TRUTH = {
    "l147r": {"model_mutation": "L147R", "pos": 147, "wt": "LEU", "to": "ARG",
              "exp": "L147R gains cortisol (ΔΔG_bind favorable for cortisol vs WT)"},
    "f119w": {"model_mutation": "F119W", "pos": 119, "wt": "PHE", "to": "TRP",
              "exp": "F119W boosts test/prog affinity"},
}
ENGINES = {
    "gromacs": ["gmx", "gmx_mpi"],
    "pmx": None,        # python import
    "openfe": None,     # python import
    "ambertools": ["tleap", "sander", "pmemd"],
}


def cmd_check(args):
    found = {}
    for tool in ("gmx", "gmx_mpi", "tleap", "sander", "pmemd"):
        found[tool] = shutil.which(tool)
    for mod in ("pmx", "openfe", "openmm", "parmed", "MDAnalysis"):
        try:
            __import__(mod); found[mod] = "import-OK"
        except Exception:
            found[mod] = None
    print("=== FEP/MD engine availability ===")
    for k, v in found.items():
        print(f"  {k:12s} {'-- not found' if not v else v}")
    any_engine = found.get("gmx") or found.get("pmx") == "import-OK" \
        or found.get("openfe") == "import-OK"
    print(f"\nRBFE-ready: {'YES' if any_engine else 'NO — install GROMACS+pmx (see SETUP_FEP.md)'}")
    return found


def cmd_prepare(args):
    gt = GROUND_TRUTH.get(args.variant)
    assert gt, f"unknown variant {args.variant}; known {list(GROUND_TRUTH)}"
    out = os.path.abspath(args.out_dir)
    os.makedirs(out, exist_ok=True)

    # endpoint complexes from existing Boltz holo poses (WT and mutant) for this ligand
    wt_holo = (f"results/stage1_wt_validation/boltz/seed1/boltz_results_inputs/"
               f"predictions/wt_{args.ligand}/wt_{args.ligand}_model_0.pdb")
    mut_holo = (f"results/stage1d_mutants/{args.variant}/boltz/seed1/boltz_results_inputs/"
                f"predictions/{args.variant}_{args.ligand}/{args.variant}_{args.ligand}_model_0.pdb")
    spec = {
        "rbfe_type": "protein_point_mutation",
        "variant": args.variant, "model_mutation": gt["model_mutation"],
        "mutation": {"pos_model": gt["pos"], "wt": gt["wt"], "to": gt["to"],
                     "chains": ["A", "B"]},
        "ligand": args.ligand,
        "endpoints": {
            "bound_WT": wt_holo, "bound_MUT": mut_holo,
            "apo_WT": "results/stage3_apo/wt/.../wt_apo_model_0.pdb (Boltz apo)",
            "apo_MUT": f"results/stage3_apo/{args.variant}/.../{args.variant}_apo_model_0.pdb",
        },
        "thermodynamic_cycle": "ddG_bind = dG_bound(WT->mut) - dG_apo(WT->mut)",
        "engine_recommended": "pmx + GROMACS (non-equilibrium TI, hybrid topology)",
        "lambda_windows": 21, "ns_per_window": 5,
        "exp_expectation": gt["exp"],
        "status": "PREPARED — execution gated on GROMACS/pmx install (see SETUP_FEP.md)",
    }
    json.dump(spec, open(os.path.join(out, "rbfe_spec.json"), "w"), indent=2)
    # copy available endpoint structures
    for tag, p in (("bound_WT", wt_holo), ("bound_MUT", mut_holo)):
        if os.path.exists(p):
            shutil.copy(p, os.path.join(out, f"{tag}.pdb"))
    print(f"[fep] prepared RBFE prototype for {args.variant}+{args.ligand} -> {out}")
    print(f"      cycle: {spec['thermodynamic_cycle']}")
    print(f"      expectation: {gt['exp']}")
    found = cmd_check(args)
    if not (found.get("gmx") or found.get("pmx") == "import-OK"):
        _write_setup(out)
        print(f"      -> wrote SETUP_FEP.md (engine not installed; execution deferred)")


def _write_setup(out):
    setup = """# FEP (RBFE) setup — required to run Tier-2

Tier-2 protein-mutation RBFE needs an alchemical engine. Recommended: **pmx + GROMACS**.

## Install
1. GROMACS (>=2023, with free-energy + non-equilibrium support):
     conda create -n fep -c conda-forge gromacs openmm
2. pmx (protein mutation FEP toolkit):
     pip install pmx   # or: git clone github.com/deGrootLab/pmx && pip install -e .
   (Alternative engines: OpenFE for ligand RBFE; Amber TI via pmemd.)

## Protocol (per prepared prototype rbfe_spec.json)
1. Build hybrid topology for the mutation (Leu->Arg) with pmx (`pmx mutate` + `pmx gentop`).
2. Solvate + ionize both BOUND (protein+ligand) and APO endpoints.
3. Equilibrate (drMD restraints available at ~/Constrained_md/drmd_restraints.yaml).
4. Non-equilibrium TI: 21 lambda windows x ~5 ns, both directions; BAR/Crooks estimate.
5. ddG_bind = dG_bound(WT->mut) - dG_apo(WT->mut).

## Validation target
Run on WT<->L147R with cortisol first; expect ddG_bind favorable for cortisol in L147R
(matches experiment). If reproduced, the cycle/topology is validated and Tier-2 can judge
the elite estradiol designs.
"""
    open(os.path.join(out, "SETUP_FEP.md"), "w").write(setup)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.set_defaults(func=cmd_check)
    p = sub.add_parser("prepare")
    p.add_argument("--variant", default="l147r")
    p.add_argument("--ligand", default="cortisol")
    p.add_argument("--out_dir", required=True)
    p.set_defaults(func=cmd_prepare)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
