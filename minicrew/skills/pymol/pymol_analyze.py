"""Headless PyMOL structural analysis -> JSON report (for the minicrew PyMOL tool).

Loads a protein-ligand complex (PDB or Boltz/Protenix .cif), finds the ligand,
the pocket residues around it, and the polar (H-bond-like) ligand<->protein
contacts with distances. Prints ONE line of JSON to stdout so a caller can parse
it. Optionally renders a PNG.

Run with a PyMOL that imports `pymol` (e.g. the conda pyrosetta env):
    ~/.conda/envs/pyrosetta/bin/pymol -cq tfsensor/pymol_analyze.py -- \
        <structure.pdb|.cif> [lig_resname] [pocket_cutoff=5.0] [out_png]
"""
import json
import os
import sys

from pymol import cmd


def _args():
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    pdb = argv[0]
    lig = argv[1] if len(argv) > 1 and argv[1] not in ("", "None", "auto") else None
    cutoff = float(argv[2]) if len(argv) > 2 and argv[2] else 5.0
    out_png = argv[3] if len(argv) > 3 and argv[3] else None
    return pdb, lig, cutoff, out_png


def analyze(pdb, lig_resn=None, cutoff=5.0, out_png=None):
    if not os.path.exists(pdb):
        return {"error": f"file not found: {pdb}"}
    cmd.load(pdb, "s")
    cmd.remove("solvent")

    # locate the ligand: explicit resname, else the largest non-polymer organic group
    if lig_resn:
        cmd.select("lig", f"resn {lig_resn} and not polymer")
    else:
        cmd.select("lig", "(not polymer) and (not solvent) and (not inorganic)")
    n_lig = cmd.count_atoms("lig")
    if n_lig == 0:
        # fall back: any organic hetero atoms
        cmd.select("lig", "organic and not polymer")
        n_lig = cmd.count_atoms("lig")
    if n_lig == 0:
        return {"error": "no ligand / heteroatom group found", "pdb": os.path.basename(pdb)}

    lig_resns = set()
    cmd.iterate("lig", "R.add(resn)", space={"R": lig_resns})

    # pocket residues within cutoff of the ligand
    cmd.select("pocket", f"byres (polymer within {cutoff} of lig)")
    pocket = []
    seen = set()
    cmd.iterate("pocket and name CA",
                "P.append((chain, resi, resn))", space={"P": pocket})
    pocket = [f"{c}/{rn}{ri}" for (c, ri, rn) in pocket
              if (c, ri) not in seen and not seen.add((c, ri))]

    # polar (H-bond-like) contacts: ligand N/O <-> protein N/O within 3.5 A
    labels = {}
    cmd.iterate("lig or (polymer and (elem N+O))",
                "L[(model, index)] = (chain, resi, resn, name)", space={"L": labels})
    pairs = cmd.find_pairs("lig and (elem N+O)",
                           "polymer and (elem N+O)", cutoff=3.5)
    contacts = []
    for a, b in pairs:
        la, lb = labels.get(a), labels.get(b)
        if not la or not lb:
            continue
        try:
            d = cmd.get_distance(f"{a[0]} and index {a[1]}",
                                 f"{b[0]} and index {b[1]}")
        except Exception:
            continue
        contacts.append({
            "ligand_atom": f"{la[2]}.{la[3]}",
            "residue": f"{lb[0]}/{lb[2]}{lb[1]}.{lb[3]}",
            "distance_A": round(float(d), 2),
        })
    contacts.sort(key=lambda c: c["distance_A"])

    report = {
        "pdb": os.path.basename(pdb),
        "ligand_resnames": sorted(lig_resns),
        "n_ligand_atoms": n_lig,
        "n_pocket_residues": len(pocket),
        "pocket_residues": pocket,
        "n_polar_contacts": len(contacts),
        "polar_contacts": contacts,
        "pocket_cutoff_A": cutoff,
    }

    if out_png:
        cmd.hide("everything")
        cmd.show("cartoon", "polymer")
        cmd.show("sticks", "lig or pocket")
        cmd.util.cbag("pocket")
        cmd.util.cbay("lig")
        cmd.orient("lig")
        cmd.zoom("lig", 6)
        cmd.set("ray_opaque_background", 0)
        cmd.png(out_png, width=1000, height=800, dpi=150, ray=1)
        report["image"] = out_png
    return report


# NB: run at top level — PyMOL execs scripts with __name__ != "__main__".
_pdb, _lig, _cutoff, _out_png = _args()
try:
    _rep = analyze(_pdb, _lig, _cutoff, _out_png)
except Exception as exc:
    _rep = {"error": f"pymol analysis failed: {exc}"}
sys.stdout.write("PYMOL_JSON:" + json.dumps(_rep) + "\n")
sys.stdout.flush()
