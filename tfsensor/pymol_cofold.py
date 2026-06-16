"""Render the full co-folded AcrR(dimer)+steroid complex (Boltz prediction).

Clean publication overview: chain A and chain B cartoons in two colours, the
co-folded ligand shown prominently as sticks + spheres, white background, ray traced.

  pymol -cq tfsensor/pymol_cofold.py -- <pose.pdb> <out_png> [lig_resn=LIG]
"""
import sys
from pymol import cmd

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
pose = argv[0]
out_png = argv[1]
lig_resn = argv[2] if len(argv) > 2 else "LIG"

cmd.reinitialize()
cmd.load(pose, "cx")
cmd.bg_color("white")
cmd.hide("everything")

# dimer cartoon, two colours
cmd.show("cartoon", "polymer")
cmd.color("teal", "polymer and chain A")
cmd.color("wheat", "polymer and chain B")
cmd.set("cartoon_transparency", 0.0)

# co-folded ligand: sticks + translucent spheres so it pops
lig = f"resn {lig_resn}"
cmd.show("sticks", lig)
cmd.set_bond("stick_radius", 0.30, lig)
cmd.show("spheres", lig)
cmd.set("sphere_scale", 0.32, lig)
cmd.color("magenta", f"{lig} and elem C")
cmd.util.cnc(lig)

# faint pocket-residue context (no labels in the overview)
cmd.show("sticks", "chain A and resi 106+119+123+147 and not name N+C+O")
cmd.color("yellow", "chain A and resi 106+119+123+147 and elem C")
cmd.util.cnc("chain A and resi 106+119+123+147")

cmd.set("ray_shadows", 0)
cmd.set("ray_opaque_background", 1)
cmd.set("antialias", 2)
cmd.set("ambient", 0.35)
cmd.set("cartoon_fancy_helices", 1)
cmd.orient("polymer")
cmd.turn("y", 10)
cmd.ray(2200, 1700)
cmd.png(out_png, dpi=300)
cmd.save(out_png.replace(".png", ".pse"))
print(f"[pymol] wrote {out_png} (+ .pse)")
