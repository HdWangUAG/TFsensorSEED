"""Auto-detected ligand–pocket interaction figure (publication style).

Selects the cognate protomer's binding-site residues — any residue with an atom
within CUTOFF Å of the ligand — and renders them as labelled sticks, the ligand as
sticks, and polar contacts (candidate H-bonds, ≤3.5 Å heavy-atom) as dashed lines.
Design-mutation positions (--mut) are highlighted orange. Labels = MODEL numbering,
read from the actual model (correct for mutants).

Run headless:
  pymol -cq tfsensor/pymol_interactions.py -- <pose.pdb> <out.png> [lig_chain=L] [mut=61,88] [title]
"""
import sys
from pymol import cmd

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
pose, out_png = argv[0], argv[1]
lig_chain = argv[2] if len(argv) > 2 and argv[2] else "L"
mut = [int(x) for x in argv[3].split(",")] if len(argv) > 3 and argv[3] else []
title = argv[4] if len(argv) > 4 else ""
PROT_CHAIN = "A"
CUTOFF = 4.5

THREE2ONE = {"ALA":"A","ARG":"R","ASN":"N","ASP":"D","CYS":"C","GLN":"Q","GLU":"E",
             "GLY":"G","HIS":"H","ILE":"I","LEU":"L","LYS":"K","MET":"M","PHE":"F",
             "PRO":"P","SER":"S","THR":"T","TRP":"W","TYR":"Y","VAL":"V"}

cmd.reinitialize()
cmd.load(pose, "cx")
cmd.bg_color("white")
cmd.hide("everything")

lig = f"resn LIG and chain {lig_chain}"
if cmd.count_atoms(lig) == 0:
    lig = "resn LIG"

# binding-site residues: any residue with an atom within CUTOFF of the ligand
cmd.select("pocket", f"byres (polymer within {CUTOFF} of ({lig}))")

# protein cartoon, faint
cmd.show("cartoon", "polymer")
cmd.set("cartoon_transparency", 0.7, "polymer")
cmd.color("gray80", "polymer")
cmd.set("cartoon_side_chain_helper", 1)

# ligand sticks
cmd.show("sticks", lig)
cmd.set_bond("stick_radius", 0.24, lig)
cmd.color("yellow", f"{lig} and elem C")
cmd.util.cnc(lig)

# pocket residues as labelled sticks
n_pocket = n_mut = 0
for at in cmd.get_model("pocket and name CA").atom:
    resi, ch, resn = at.resi, at.chain, at.resn
    sel = f"chain {ch} and resi {resi}"
    cmd.show("sticks", f"{sel} and not (name N+C+O and not resn PRO)")
    is_mut = (int(resi) in mut and ch == PROT_CHAIN)
    cmd.color("orange" if is_mut else "palecyan", f"{sel} and elem C")
    cmd.util.cnc(sel)
    n_pocket += 1
    n_mut += int(is_mut)
    lab = f"{THREE2ONE.get(resn, resn)}{resi}" + ("*" if is_mut else "")
    anchor = f"{sel} and name CB"
    if cmd.count_atoms(anchor) == 0:
        anchor = f"{sel} and name CA"
    cmd.label(anchor, f'"{lab}"')

# candidate H-bonds: ligand polar atoms <-> pocket polar atoms
cmd.distance("hbonds", f"({lig}) and (elem N+O)", "pocket and (elem N+O)", 3.5, mode=2)
cmd.color("red", "hbonds")
cmd.hide("labels", "hbonds")

# style + framing
cmd.set("label_size", 15)
cmd.set("label_color", "black")
cmd.set("label_outline_color", "white")
cmd.set("dash_width", 3.0)
cmd.set("dash_gap", 0.35)
cmd.orient(f"({lig}) or pocket")
cmd.zoom(f"({lig}) or pocket", 1.5)
if title:
    cmd.set("title", title)

cmd.set("ray_shadows", 0)
cmd.set("ray_opaque_background", 1)
cmd.set("antialias", 2)
cmd.set("depth_cue", 0)
cmd.set("ambient", 0.45)
cmd.ray(2200, 1600)
cmd.png(out_png, dpi=300)
cmd.save(out_png.replace(".png", ".pse"))
print(f"[pymol] {out_png}: {n_pocket} pocket residues ({n_mut} design mutations), ligand={lig}")
