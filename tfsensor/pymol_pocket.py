"""Render the AcrR holo pocket (key residues + co-folded ligand) for review.

Publication-style PyMOL figure: AcrR dimer cartoon (semi-transparent), the bound
steroid as sticks, and the mechanistically key pocket residues as labelled sticks.
ALL labels use the MODEL/design numbering (the index we design on), e.g. "F119".

Key residues (model numbering, chain A):
  Q88  W96  E106(candidate phenol clamp)  F119(F119W site)
  R123(3-keto reader)  L147(L147R site)

Run headless:
  pymol -cq tfsensor/pymol_pocket.py -- <pose.pdb> <out_png> [lig_resn=LIG] [lig_chain=L]
"""
import sys
from pymol import cmd

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
pose = argv[0]
out_png = argv[1]
lig_resn = argv[2] if len(argv) > 2 else "LIG"
lig_chain = argv[3] if len(argv) > 3 else "L"
title = argv[4] if len(argv) > 4 else ""

THREE2ONE = {"ALA":"A","ARG":"R","ASN":"N","ASP":"D","CYS":"C","GLN":"Q",
             "GLU":"E","GLY":"G","HIS":"H","ILE":"I","LEU":"L","LYS":"K",
             "MET":"M","PHE":"F","PRO":"P","SER":"S","THR":"T","TRP":"W",
             "TYR":"Y","VAL":"V"}
# (model_resi, one-letter, role, is_mutation_site)
KEYRES = [
    (88,  "Q", "", False),
    (96,  "W", "", False),
    (106, "E", "candidate phenol clamp", False),
    (119, "F", "F119W site", True),
    (123, "R", "3-keto reader", False),
    (147, "L", "L147R site", True),
]
CHAIN = "A"

cmd.reinitialize()
cmd.load(pose, "cx")
cmd.bg_color("white")
cmd.hide("everything")

# protein cartoon, faint
cmd.show("cartoon", "polymer")
cmd.set("cartoon_transparency", 0.55, "polymer")
cmd.color("gray80", "polymer")
cmd.set("cartoon_side_chain_helper", 1)

# ligand
lig_sel = f"resn {lig_resn} and chain {lig_chain}"
if cmd.count_atoms(lig_sel) == 0:
    lig_sel = f"resn {lig_resn}"
cmd.show("sticks", lig_sel)
cmd.set_bond("stick_radius", 0.22, lig_sel)
cmd.color("cyan", f"{lig_sel} and elem C")
cmd.util.cnc(lig_sel)

# key residues
mut_sel = []
for resi, aa, role, is_mut in KEYRES:
    sel = f"chain {CHAIN} and resi {resi}"
    if cmd.count_atoms(sel) == 0:
        continue
    cmd.show("sticks", f"{sel} and not name N+C+O")
    ccol = "orange" if is_mut else "yellow"
    cmd.color(ccol, f"{sel} and elem C")
    cmd.util.cnc(f"{sel}")
    if is_mut:
        mut_sel.append(sel)
    # read the ACTUAL residue identity from the model (correct for mutants)
    real = THREE2ONE.get(cmd.get_model(f"{sel} and name CA").atom[0].resn, aa) \
        if cmd.count_atoms(f"{sel} and name CA") else aa
    lab = f"{real}{resi}"                     # MODEL numbering only
    if is_mut and real != aa:
        lab += f" ({aa}{resi}{real})"         # e.g. F119W (model index)
    if role:
        lab += f" [{role}]"
    # label on CB (fallback CA)
    anchor = f"{sel} and name CB"
    if cmd.count_atoms(anchor) == 0:
        anchor = f"{sel} and name CA"
    cmd.label(anchor, f'"{lab}"')

# polar contacts between ligand and key polar residues (E106/R123/Q88/Q151/S144)
cmd.distance("hbonds", lig_sel,
             f"chain {CHAIN} and resi 106+123+88+144 and (elem N+O)", 3.6, mode=2)
cmd.color("red", "hbonds")
cmd.hide("labels", "hbonds")

# view + style
cmd.set("label_size", 16)
cmd.set("label_color", "black")
cmd.set("label_outline_color", "white")
cmd.set("stick_radius", 0.16, "chain A and not (" + lig_sel + ")")
cmd.orient(f"({lig_sel}) or (chain {CHAIN} and resi 106+119+123+147)")
cmd.zoom(f"({lig_sel}) or (chain {CHAIN} and resi 106+119+123+147)", 2.5)

cmd.set("ray_shadows", 0)
cmd.set("ray_opaque_background", 1)
cmd.set("antialias", 2)
cmd.set("depth_cue", 0)
cmd.set("ambient", 0.4)
cmd.ray(2000, 1500)
cmd.png(out_png, dpi=300)
# also save a session for interactive review
cmd.save(out_png.replace(".png", ".pse"))
print(f"[pymol] wrote {out_png} (+ .pse session)")
