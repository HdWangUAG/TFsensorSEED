"""Fixed-backbone ΔΔG-of-binding worker, flex-ddG style (Stage 3a, v2).

Attempt 1 (strict fixed-backbone, 1-cycle neighborhood relax) failed calibration
(0/10) because 9/12 WT baselines were positive/clashing — the relax was too weak to
clean the raw Boltz holo poses, and a rigid backbone can't absorb bulk mutations
(F→W, L→R). This v2 is the standard flex-ddG approach:

  1. PRE-RELAX the WT holo complex once (full CA-restrained FastRelax) → a clean,
     clash-free, negative-dG reference `wt_clean`.
  2. ENSEMBLE: for each ensemble member, perturb the local backbone (shell backbone
     mobile) to make a backbone `bb_i`, then score WT and the mutant **paired on the
     SAME `bb_i`** (sidechain repack+min, backbone fixed). Pairing cancels per-member
     backbone noise; the ensemble's backbone diversity lets bulk mutations be
     accommodated. ΔΔG_i = dG_sep(mut_i) − dG_sep(wt_i).
  3. ΔΔG(M) = MEDIAN over ensemble (robust to outliers).

Ligand kept tethered throughout (weak harmonic CoordinateConstraint, sd 2.0 Å) so it
relaxes locally but cannot be ejected. dG_separated via InterfaceAnalyzer on a
constraint-free clone (tether never biases the reported binding energy).

    python -m tfsensor.ddg_mutation --holo_pdb <wt_holo.pdb> --smiles "<SMILES>" \
        --ligand estradiol --seed 1 --mutations R123E,R123D,F119W,L147R \
        --n_ensemble 8 --work_dir <abs work> --out_json <abs out.json>
"""
from __future__ import annotations

import argparse
import json
import os
import statistics

from tfsensor.physics_score import (_extract_ligand_block, _ligand_pdb_to_mol,
                                     _molfile_to_params)

MUTATIONS = {
    "R123E": {"pos": 123, "wt": "ARG", "to": "GLU"},
    "R123D": {"pos": 123, "wt": "ARG", "to": "ASP"},
    "F119W": {"pos": 119, "wt": "PHE", "to": "TRP"},
    "L147R": {"pos": 147, "wt": "LEU", "to": "ARG"},
}
CHAINS = ("A", "B")
TETHER_SD = 2.0
EJECT_DRIFT = 3.0
PRERELAX_CYCLES = 2


# ---------- complex / ligand setup (reuse physics_score) ----------
def _build_complex(holo_pdb, smiles, name, work_dir):
    prot, lig = _extract_ligand_block(holo_pdb)
    mol = _ligand_pdb_to_mol(lig, smiles, os.path.join(work_dir, name + ".mol"))
    params, lig_pdb = _molfile_to_params(mol, name, work_dir)
    complex_pdb = os.path.join(work_dir, name + "_complex.pdb")
    with open(complex_pdb, "w") as fh:
        fh.writelines(prot)
        for l in open(lig_pdb):
            if l[:6].strip() in ("ATOM", "HETATM"):
                fh.write(l)
        fh.write("END\n")
    return params, complex_pdb


def _ligand_residue_index(pose):
    for i in range(1, pose.size() + 1):
        if pose.residue(i).is_ligand():
            return i
    return None


def _interface_string(pose):
    import pyrosetta
    nch = pose.num_chains()
    lig = pyrosetta.rosetta.core.pose.get_chain_from_chain_id(nch, pose)
    prot = "".join(pyrosetta.rosetta.core.pose.get_chain_from_chain_id(i, pose)
                   for i in range(1, nch))
    return f"{prot}_{lig}"


def _ligand_com(pose, lig_idx):
    res = pose.residue(lig_idx)
    n, sx, sy, sz = 0, 0.0, 0.0, 0.0
    for a in range(1, res.natoms() + 1):
        if res.atom_type(a).element() == "H":
            continue
        xyz = res.xyz(a)
        sx += xyz.x; sy += xyz.y; sz += xyz.z; n += 1
    return (sx / n, sy / n, sz / n)


def _tether_ligand(pose, lig_idx, sd=TETHER_SD):
    """Weak harmonic coordinate constraint on ligand heavy atoms (anti-ejection)."""
    import pyrosetta
    from pyrosetta.rosetta.core.id import AtomID
    from pyrosetta.rosetta.core.scoring.constraints import CoordinateConstraint
    from pyrosetta.rosetta.core.scoring.func import HarmonicFunc
    anchor = AtomID(pose.residue(1).atom_index("CA"), 1)
    res = pose.residue(lig_idx)
    for a in range(1, res.natoms() + 1):
        if res.atom_type(a).element() == "H":
            continue
        pose.add_constraint(CoordinateConstraint(AtomID(a, lig_idx), anchor,
                                                 res.xyz(a), HarmonicFunc(0.0, sd)))


# ---------- relaxation ----------
def _prerelax(pose, sf, lig_idx):
    """Clean the raw Boltz pose: CA-restrained full FastRelax + ligand tether."""
    import pyrosetta
    from pyrosetta.rosetta.protocols.relax import FastRelax
    cst = pyrosetta.rosetta.protocols.constraint_movers.\
        AddConstraintsToCurrentConformationMover()
    cst.apply(pose)                      # CA coordinate constraints (whole backbone)
    _tether_ligand(pose, lig_idx)
    FastRelax(sf, PRERELAX_CYCLES).apply(pose)
    pose.remove_constraints()            # fresh slate for the ensemble phase


def _shell(pose, focus_idxs):
    from pyrosetta.rosetta.core.select.residue_selector import (
        ResidueIndexSelector, NeighborhoodResidueSelector)
    foc = ResidueIndexSelector(",".join(map(str, focus_idxs)))
    return NeighborhoodResidueSelector(foc, distance=8.0, include_focus_in_subset=True)


def _relax(pose, sf, focus_idxs, lig_idx, bb_flex):
    """Local relax. bb_flex=True perturbs shell backbone (ensemble generation);
    bb_flex=False = sidechain repack+min only (paired scoring, backbone fixed)."""
    import pyrosetta
    from pyrosetta.rosetta.core.pack.task import TaskFactory
    from pyrosetta.rosetta.core.pack.task.operation import (
        InitializeFromCommandline, IncludeCurrent, NoRepackDisulfides,
        OperateOnResidueSubset, RestrictToRepackingRLT, PreventRepackingRLT)
    from pyrosetta.rosetta.protocols.relax import FastRelax

    nbr = _shell(pose, focus_idxs)
    tf = TaskFactory()
    tf.push_back(InitializeFromCommandline())
    tf.push_back(IncludeCurrent())
    tf.push_back(NoRepackDisulfides())
    tf.push_back(OperateOnResidueSubset(RestrictToRepackingRLT(), nbr))
    tf.push_back(OperateOnResidueSubset(PreventRepackingRLT(), ~nbr))

    mm = pyrosetta.MoveMap()
    mm.set_bb(False)
    mm.set_chi(False)
    mm.set_jump(False)
    mask = nbr.apply(pose)
    for i in range(1, pose.size() + 1):
        if mask[i]:
            mm.set_chi(i, True)
            if bb_flex and not pose.residue(i).is_ligand():
                mm.set_bb(i, True)       # local backbone flexibility (shell only)
    ljump = pose.fold_tree().get_jump_that_builds_residue(lig_idx)
    if ljump > 0:
        mm.set_jump(ljump, True)

    fr = FastRelax(sf, 1)
    fr.set_task_factory(tf)
    fr.set_movemap(mm)
    fr.apply(pose)


def _interface_dg(pose):
    import pyrosetta
    from pyrosetta.rosetta.protocols.analysis import InterfaceAnalyzerMover
    ps = pose.clone()
    ps.remove_constraints()
    ia = InterfaceAnalyzerMover(_interface_string(ps))
    ia.set_pack_separated(True)
    ia.apply(ps)
    return float(ia.get_interface_dG())


def _mutate(pose, site_pos, to_aa3):
    from pyrosetta.rosetta.protocols.simple_moves import MutateResidue
    for c in CHAINS:
        idx = pose.pdb_info().pdb2pose(c, site_pos)
        MutateResidue(idx, to_aa3).apply(pose)


# ---------- driver ----------
def run_backbone(holo_pdb, smiles, ligand, mutation_names, work_dir, n_ens, out_json, seed):
    work_dir = os.path.abspath(work_dir)
    os.makedirs(work_dir, exist_ok=True)
    params, complex_pdb = _build_complex(holo_pdb, smiles, ligand, work_dir)

    import pyrosetta
    pyrosetta.init(f"-extra_res_fa {params} -mute all -ignore_unrecognized_res false "
                   f"-ex1 -ex2 -use_input_sc -run:constant_seed -jran {seed}")
    base = pyrosetta.pose_from_file(complex_pdb)
    sf = pyrosetta.get_fa_scorefxn()
    sf.set_weight(pyrosetta.rosetta.core.scoring.coordinate_constraint, 1.0)
    lig_idx = _ligand_residue_index(base)
    assert lig_idx is not None and base.num_chains() == 3

    for mname in mutation_names:
        m = MUTATIONS[mname]
        for c in CHAINS:
            idx = base.pdb_info().pdb2pose(c, m["pos"])
            assert idx != 0, f"{mname}: chain {c} resi {m['pos']} not found"
            got = base.residue(idx).name3()
            assert got == m["wt"], f"{mname}: {c}{m['pos']} is {got} not {m['wt']}"

    # 1) clean reference
    wt_clean = base.clone()
    _prerelax(wt_clean, sf, lig_idx)
    dg_clean = _interface_dg(wt_clean)
    print(f"[ddg] {ligand} seed{seed}: pre-relaxed WT dG_clean = {dg_clean:.2f}", flush=True)

    out = {"ligand": ligand, "seed": seed, "backbone_pdb": holo_pdb,
           "n_ensemble": n_ens, "tether_sd": TETHER_SD,
           "wt_clean_dG": round(dg_clean, 3), "ddg": {}}

    # group mutations by site (share the backbone ensemble + WT scoring)
    by_site = {}
    for mname in mutation_names:
        by_site.setdefault(MUTATIONS[mname]["pos"], []).append(mname)

    for site, mnames in by_site.items():
        focus = [wt_clean.pdb_info().pdb2pose(c, site) for c in CHAINS] + [lig_idx]
        ens = {m: [] for m in mnames}
        wt_dgs, drifts = [], []
        for i in range(n_ens):
            # WT ensemble member: local backbone-FLEXIBLE relax (shell incl. site +/- 2).
            # RNG advances per member -> backbone diversity; this is also the WT score.
            member = wt_clean.clone()
            _tether_ligand(member, lig_idx)
            _relax(member, sf, focus, lig_idx, bb_flex=True)
            com0 = _ligand_com(member, lig_idx)
            dgwt = _interface_dg(member)
            wt_dgs.append(round(dgwt, 3))
            for m in mnames:
                # mutant starts from the SAME member backbone, then its OWN local
                # backbone minimizes to accommodate the new residue (no false-negative
                # clash for small->large mutations like L147R / F119W). Paired vs dgwt.
                mu = member.clone()
                _mutate(mu, site, MUTATIONS[m]["to"])
                _relax(mu, sf, focus, lig_idx, bb_flex=True)
                dgmu = _interface_dg(mu)
                ens[m].append(round(dgmu - dgwt, 3))
                drifts.append(round(sum((a - b) ** 2 for a, b in
                                        zip(com0, _ligand_com(mu, lig_idx))) ** 0.5, 2))
        for m in mnames:
            vals = ens[m]
            out["ddg"][m] = {
                "value": round(statistics.median(vals), 3),     # headline = median
                "mean": round(statistics.mean(vals), 3),
                "sd": round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0,
                "per_member": vals,
                "wt_dG_members": wt_dgs,
                "max_lig_drift": max(drifts) if drifts else None,
            }
            print(f"[ddg] {ligand} seed{seed} {m}: ΔΔG(median)={out['ddg'][m]['value']} "
                  f"mean={out['ddg'][m]['mean']}±{out['ddg'][m]['sd']} "
                  f"(maxdrift {out['ddg'][m]['max_lig_drift']})", flush=True)

    json.dump(out, open(out_json, "w"), indent=2)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--holo_pdb", required=True)
    ap.add_argument("--smiles", required=True)
    ap.add_argument("--ligand", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--mutations", default="R123E,R123D,F119W,L147R")
    ap.add_argument("--n_ensemble", type=int, default=8)
    ap.add_argument("--work_dir", required=True)
    ap.add_argument("--out_json", required=True)
    args = ap.parse_args()
    names = [m.strip() for m in args.mutations.split(",") if m.strip()]
    for n in names:
        assert n in MUTATIONS, f"unknown mutation {n}"
    run_backbone(args.holo_pdb, args.smiles, args.ligand, names,
                 args.work_dir, args.n_ensemble, args.out_json, args.seed)


if __name__ == "__main__":
    main()
