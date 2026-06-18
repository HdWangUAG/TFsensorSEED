"""Extract a binding pocket from a protein–ligand complex for ML featurization.

Thin wrapper over the battle-tested, dependency-free PDB machinery in
``tfsensor.prep_receptor`` (``parse_pdb`` + ``pocket_scan``) — no BioPython, per
the LC-SEED golden rule. The AcrR contact maps use a 4.5 Å cutoff; here we use a
wider **8 Å** so the model sees second-shell context (per the plan).

Output schema matches the existing ``data/pocket_residues.json`` (chain / resSeq /
resName / min_dist) and additionally carries each pocket residue's Cα coordinate
and the selected ligand's heavy-atom coordinates — what the ligand/pocket graph
featurizers need downstream.

CLI:
    ~/LC-Seed/envs/app/.venv/bin/python -m tfsensor.ml.data.pocket_extract \
        --holo data/AcrR_STR_001.pdb --lig_resname STR --cutoff 8.0
"""
from __future__ import annotations

import argparse
import json

from tfsensor.prep_receptor import parse_pdb, pocket_scan

DEFAULT_CUTOFF = 8.0


def _select_ligand(ligand_atoms, lig_resname=None, lig_chain=None):
    """Filter parsed HETATM atoms to one ligand (by resName and/or chain)."""
    sel = ligand_atoms
    if lig_resname is not None:
        sel = [a for a in sel if a[1] == lig_resname]
    if lig_chain is not None:
        sel = [a for a in sel if a[0] == lig_chain]
    return sel


def extract_pocket(pdb_path, lig_resname=None, lig_chain=None,
                   cutoff=DEFAULT_CUTOFF):
    """Return a pocket dict for one protein–ligand complex.

    {
      "pdb": <path>, "lig_resname": ..., "cutoff": ...,
      "residues": [ {chain, resSeq, resName, min_dist, ca: [x,y,z] | None}, ... ],
      "ligand_atoms": [ {atom, xyz: [x,y,z]}, ... ],
    }

    Reuses ``pocket_scan`` for the contact selection so the residue set is
    identical in definition to the rest of the pipeline, just at a wider cutoff.
    """
    chains, ligand_atoms = parse_pdb(pdb_path)
    lig = _select_ligand(ligand_atoms, lig_resname, lig_chain)
    if not lig:
        raise ValueError(
            f"no ligand atoms in {pdb_path} for resname={lig_resname!r} "
            f"chain={lig_chain!r} (parsed {len(ligand_atoms)} HETATM heavy atoms)")

    residues = pocket_scan(chains, lig, cutoff=cutoff)

    # attach the Cα coordinate of each selected pocket residue
    by_key = {(ch, r["resSeq"]): r for ch in chains for r in chains[ch]}
    for res in residues:
        rec = by_key.get((res["chain"], res["resSeq"]))
        ca = rec["atoms"].get("CA") if rec else None
        res["ca"] = list(ca) if ca else None

    return {
        "pdb": pdb_path,
        "lig_resname": lig_resname,
        "cutoff": cutoff,
        "residues": residues,
        "ligand_atoms": [{"atom": a[2], "xyz": list(a[3])} for a in lig],
    }


def _main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--holo", required=True)
    ap.add_argument("--lig_resname", default=None,
                    help="restrict to this HETATM resName (e.g. STR)")
    ap.add_argument("--lig_chain", default=None)
    ap.add_argument("--cutoff", type=float, default=DEFAULT_CUTOFF)
    ap.add_argument("--out", default=None, help="write pocket JSON here")
    args = ap.parse_args()
    pocket = extract_pocket(args.holo, args.lig_resname, args.lig_chain, args.cutoff)
    n_ca = sum(1 for r in pocket["residues"] if r["ca"])
    print(f"{len(pocket['residues'])} pocket residues @ {args.cutoff} Å "
          f"({n_ca} with Cα); {len(pocket['ligand_atoms'])} ligand atoms")
    if args.out:
        json.dump(pocket, open(args.out, "w"), indent=2)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    _main()
