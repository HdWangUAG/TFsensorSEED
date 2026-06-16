"""Rosetta interface dG on a predicted holo pose (the Track-B physics signal).

Protenix has no affinity head, so we turn its (and Boltz's) predicted pose into an
affinity-like number with a physics interface energy: PyRosetta InterfaceAnalyzer
``dG_separated`` between the AcrR protein and the steroid ligand. Lower dG = stronger
predicted binding; ranking steroids by dG is an orthogonal cross-check on the Boltz
binder-prob (and a guard against DL oversmoothing on near-isosteric steroids).

Pipeline per pose:
  1. extract the ligand heavy atoms from the predicted PDB;
  2. assign bond orders from the template SMILES (RDKit AssignBondOrdersFromTemplate)
     and write a MOL at the PREDICTED coordinates;
  3. molfile_to_params -> .params + a ligand PDB with Rosetta atom names at those coords;
  4. concatenate predicted protein chains + ligand PDB -> complex;
  5. PyRosetta InterfaceAnalyzerMover -> dG_separated.

Run in the pyrosetta env (has pyrosetta + rdkit):
    python -m tfsensor.physics_score --holo_pdb <pred_model.pdb> \
        --smiles "<steroid SMILES>" --name estradiol --work_dir /tmp/phys_estr
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys


def _extract_ligand_block(holo_pdb):
    """Return HETATM lines (heavy atoms) of the ligand and the protein ATOM lines."""
    lig, prot = [], []
    for l in open(holo_pdb):
        rec = l[:6].strip()
        if rec == "HETATM":
            resname = l[17:20].strip()
            if resname in ("HOH", "WAT"):
                continue
            el = (l[76:78].strip() or l[12:16].strip()[0]).upper()
            if el == "H":
                continue
            lig.append(l)
        elif rec in ("ATOM", "TER"):
            prot.append(l)
    return prot, lig


def _ligand_pdb_to_mol(lig_lines, smiles, out_mol):
    """Build an RDKit mol at the predicted coords with bonds from the template."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    # write a minimal PDB of just the ligand for RDKit to read coordinates
    tmp_pdb = out_mol + ".lig.pdb"
    with open(tmp_pdb, "w") as fh:
        fh.writelines(lig_lines)
        fh.write("END\n")
    raw = Chem.MolFromPDBFile(tmp_pdb, removeHs=True, sanitize=False)
    if raw is None:
        raise RuntimeError("RDKit could not read predicted ligand PDB")
    template = Chem.MolFromSmiles(smiles)
    mol = AllChem.AssignBondOrdersFromTemplate(template, raw)
    mol = Chem.AddHs(mol, addCoords=True)
    Chem.MolToMolFile(mol, out_mol)
    return out_mol


def _molfile_to_params(mol_path, name, work_dir):
    """Run LC-SEED's molfile_to_params; return (params_path, ligand_pdb_path)."""
    sys.path.insert(0, os.path.expanduser("~/LC-Seed"))
    from lcseed import config  # resolves LCSEED_MOLFILE_TO_PARAMS / pyrosetta python
    m2p = None
    for cand in [os.environ.get("LCSEED_MOLFILE_TO_PARAMS")]:
        if cand and os.path.exists(cand):
            m2p = cand
    if m2p is None:  # best-effort search
        r = subprocess.run(["find", os.path.expanduser("~"), "-name",
                            "molfile_to_params.py"], capture_output=True, text=True)
        cands = [x for x in r.stdout.split() if x]
        m2p = cands[0] if cands else None
    if not m2p:
        raise RuntimeError("molfile_to_params.py not found")
    py = config.pyrosetta_python()
    subprocess.run([py, m2p, "-n", name, "--clobber", "-p",
                    os.path.join(work_dir, name), mol_path],
                   cwd=work_dir, check=True)
    return (os.path.join(work_dir, name + ".params"),
            os.path.join(work_dir, name + "_0001.pdb"))


def interface_dg(holo_pdb, smiles, name, work_dir, relax_cycles=1):
    """Return dG_separated for the protein..ligand interface of a predicted pose."""
    os.makedirs(work_dir, exist_ok=True)
    prot, lig = _extract_ligand_block(holo_pdb)
    mol = _ligand_pdb_to_mol(lig, smiles, os.path.join(work_dir, name + ".mol"))
    params, lig_pdb = _molfile_to_params(mol, name, work_dir)

    # assemble protein (chains A/B) + Rosetta-named ligand into one complex PDB
    complex_pdb = os.path.join(work_dir, name + "_complex.pdb")
    with open(complex_pdb, "w") as fh:
        fh.writelines(prot)
        for l in open(lig_pdb):
            if l[:6].strip() in ("ATOM", "HETATM"):
                fh.write(l)
        fh.write("END\n")

    import pyrosetta
    from pyrosetta.rosetta.protocols.analysis import InterfaceAnalyzerMover
    pyrosetta.init(f"-extra_res_fa {params} -mute all -ignore_unrecognized_res false")
    pose = pyrosetta.pose_from_file(complex_pdb)
    scorefxn = pyrosetta.get_fa_scorefxn()

    # Relieve raw-prediction clashes with a coordinate-constrained relax before
    # measuring dG (a raw predicted pose gives a meaningless positive dG).
    if relax_cycles > 0:
        from pyrosetta.rosetta.protocols.relax import FastRelax
        cst = pyrosetta.rosetta.protocols.constraint_movers.AddConstraintsToCurrentConformationMover()
        # CA coordinate constraints are the default (use_distance_cst() == False in
        # this PyRosetta build, where the field is read-only); apply as-is.
        cst.apply(pose)
        sf = pyrosetta.get_fa_scorefxn()
        sf.set_weight(pyrosetta.rosetta.core.scoring.coordinate_constraint, 1.0)
        fr = FastRelax(sf, relax_cycles)
        fr.apply(pose)

    # ligand is the last chain; interface = protein (A,B) vs ligand chain
    nchains = pose.num_chains()
    lig_chain = pyrosetta.rosetta.core.pose.get_chain_from_chain_id(nchains, pose)
    prot_chains = "".join(
        pyrosetta.rosetta.core.pose.get_chain_from_chain_id(i, pose)
        for i in range(1, nchains))
    iface = f"{prot_chains}_{lig_chain}"
    ia = InterfaceAnalyzerMover(iface)
    ia.set_pack_separated(True)
    ia.apply(pose)
    return {"name": name, "interface": iface,
            "dG_separated": float(ia.get_interface_dG()),
            "relax_cycles": relax_cycles,
            "complex_pdb": complex_pdb}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--holo_pdb", required=True)
    ap.add_argument("--smiles", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--work_dir", required=True)
    ap.add_argument("--relax_cycles", type=int, default=1,
                    help="constrained FastRelax cycles before dG (0 = raw pose)")
    ap.add_argument("--out_json", default=None,
                    help="write the result dict to this file (pure JSON, no log noise)")
    args = ap.parse_args()
    import json
    res = interface_dg(args.holo_pdb, args.smiles, args.name,
                       args.work_dir, args.relax_cycles)
    if args.out_json:
        json.dump(res, open(args.out_json, "w"), indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
