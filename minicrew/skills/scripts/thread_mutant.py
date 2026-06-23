"""Thread mutation(s) onto a complex with PyRosetta -> mutant PDB (+ JSON report).

Reliable side-chain swap (MutateResidue places a rotamer) for BOTH homodimer
chains. The ligand is stripped before loading (no params needed -> avoids
fill_missing_atoms), the apo protein is mutated, then the original ligand is
re-appended so the rendered pocket still shows the ligand. Used by the minicrew
pocket_mutation_view skill (headless PyMOL mutagenesis is broken under `-cq`).

    ~/.conda/envs/pyrosetta/bin/python -m tfsensor.thread_mutant \
        <complex.pdb> <I61L,L85I> <out_mutant.pdb>
"""
import json
import os
import sys

ONE2THREE = {"A": "ALA", "R": "ARG", "N": "ASN", "D": "ASP", "C": "CYS", "Q": "GLN",
             "E": "GLU", "G": "GLY", "H": "HIS", "I": "ILE", "L": "LEU", "K": "LYS",
             "M": "MET", "F": "PHE", "P": "PRO", "S": "SER", "T": "THR", "W": "TRP",
             "Y": "TYR", "V": "VAL"}
_WATERS = {"HOH", "WAT", "TIP", "DOD"}


def _parse(tok):
    return tok[0].upper(), int(tok[1:-1]), tok[-1].upper()


def main():
    pdb, muts_str, out = sys.argv[1], sys.argv[2], sys.argv[3]
    muts = [m.strip() for m in muts_str.replace(";", ",").split(",") if m.strip()]

    # split protein (ATOM) from ligand (HETATM, non-water) so the apo protein
    # loads into Rosetta without ligand params.
    atom_lines, lig_lines = [], []
    for ln in open(pdb):
        if ln.startswith("ATOM"):
            atom_lines.append(ln)
        elif ln.startswith("HETATM") and ln[17:20].strip() not in _WATERS:
            lig_lines.append(ln)
    apo = out + ".apo_in.pdb"
    open(apo, "w").write("".join(atom_lines) + "END\n")

    import pyrosetta
    from pyrosetta.rosetta.protocols.simple_moves import MutateResidue
    pyrosetta.init("-mute all -ignore_unrecognized_res true -ignore_zero_occupancy false "
                   "-load_PDB_components false")
    pose = pyrosetta.pose_from_file(apo)
    info = pose.pdb_info()
    chains = sorted({info.chain(i) for i in range(1, pose.total_residue() + 1)
                     if pose.residue(i).is_protein()})
    applied, mism = [], []
    for tok in muts:
        w, pos, m = _parse(tok)
        hit = False
        for ch in chains:
            idx = info.pdb2pose(ch, pos)
            if idx and pose.residue(idx).is_protein():
                cur = pose.residue(idx).name1()
                if cur != w:
                    mism.append(f"{tok}: chain {ch} resi {pos} is {cur}, expected {w}")
                MutateResidue(idx, ONE2THREE[m]).apply(pose)
                hit = True
        if hit:
            applied.append(tok)

    mut_apo = out + ".apo_out.pdb"
    pose.dump_pdb(mut_apo)
    # recombine mutant protein + original ligand
    prot = [ln for ln in open(mut_apo) if ln.startswith(("ATOM", "TER"))]
    open(out, "w").write("".join(prot) + "".join(lig_lines) + "END\n")
    for f in (apo, mut_apo):
        try:
            os.remove(f)
        except OSError:
            pass
    print("THREAD_JSON:" + json.dumps(
        {"applied": applied, "mismatches": mism, "chains": list(chains),
         "n_ligand_atoms": len(lig_lines), "out": out}))


if __name__ == "__main__":
    main()
