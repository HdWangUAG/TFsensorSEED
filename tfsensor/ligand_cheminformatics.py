"""Cheminformatic basis for the AcrR biosensor design rationale.

Quantifies how the steroid panel differs chemically, to justify (a) why estradiol
is a hard / distinct target and (b) why the F119W (Phe->Trp) and L147R (Leu->Arg)
pocket mutations shift specificity the way the wet-lab data show.

Key chemistry the figures make explicit:
  * estradiol      — AROMATIC A-ring + phenolic 3-OH (planar, H-bond DONOR, acidic);
                     no 4-en-3-one. The lone non-responder in WT.
  * testosterone   — 4-en-3-one A-ring (H-bond ACCEPTOR) + 17beta-OH. WT responder.
  * progesterone   — 4-en-3-one + 17-acetyl (most hydrophobic; extra ketone). WT responder.
  * cortisol       — 4-en-3-one + 11beta-OH + 17alpha-OH + 21-OH ketol (most POLAR,
                     most H-bond capacity, bulkiest). No WT response; gained by F119W;
                     becomes the preferred ligand in L147R.

Design link: cortisol's extra polarity/H-bonding & size explain why a bigger aromatic
(F119W, indole adds bulk + H-bond/pi surface) recruits it, and why a buried positive
charge / H-bond donor (L147R, Arg) selects the more polar cortisol over the less polar
testosterone — i.e. the specificity inversion.

Run in an env with rdkit + matplotlib (e.g. ~/LC-Seed/envs/app/.venv):
    python -m tfsensor.ligand_cheminformatics --panel data/steroid_panel.csv \
        --out_dir results/stage0_ligands/cheminformatics
"""
from __future__ import annotations

import argparse
import csv
import io
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager  # noqa: F401
from PIL import Image

from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, Draw, Lipinski, rdMolDescriptors
from rdkit.Chem import rdFMCS, rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D
from rdkit import DataStructs

# consistent, colourblind-friendly palette + publication rcParams
PALETTE = {"target": "#1b9e77", "responder": "#7570b3", "polar": "#d95f02",
           "nonresp": "#e7298a"}
plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 300, "font.size": 11,
    "font.family": "DejaVu Sans", "axes.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "pdf.fonttype": 42, "ps.fonttype": 42,
})

# functional-group SMARTS for highlighting / counting
SMARTS = {
    "aromatic_ring":  "c1ccccc1",
    "phenol_OH":      "[OX2H]c",
    "enone(4-en-3-one)": "[#6]=[#6][CX3]=O",
    "ketone":         "[#6][CX3](=O)[#6]",
    "hydroxyl":       "[OX2H]",
    "primary_OH(21)": "[CH2][OX2H]",
}


def load_panel(panel_csv):
    rows = []
    for r in csv.DictReader(open(panel_csv)):
        m = Chem.MolFromSmiles(r["smiles"].strip())
        rows.append({"name": r["name"].strip(), "role": r.get("role", "").strip(),
                     "smiles": r["smiles"].strip(), "mol": m})
    return rows


def descriptors(mol):
    matches = lambda sm: len(mol.GetSubstructMatches(Chem.MolFromSmarts(sm)))
    return {
        "Formula":      rdMolDescriptors.CalcMolFormula(mol),
        "MW":           round(Descriptors.MolWt(mol), 1),
        "cLogP":        round(Descriptors.MolLogP(mol), 2),
        "TPSA":         round(Descriptors.TPSA(mol), 1),
        "HBD":          Lipinski.NumHDonors(mol),
        "HBA":          Lipinski.NumHAcceptors(mol),
        "n_OH":         matches("[OX2H]"),
        "n_C=O":        matches("[CX3]=O"),
        "AromRings":    rdMolDescriptors.CalcNumAromaticRings(mol),
        "FracCSP3":     round(rdMolDescriptors.CalcFractionCSP3(mol), 2),
        "RotBonds":     Descriptors.NumRotatableBonds(mol),
        "HeavyAtoms":   mol.GetNumHeavyAtoms(),
    }


def _aligned_2d(rows):
    """Align all steroids on their shared core (MCS) for a consistent depiction."""
    mols = [r["mol"] for r in rows]
    mcs = rdFMCS.FindMCS(mols, ringMatchesRingOnly=True, completeRingsOnly=True,
                         timeout=20)
    core = Chem.MolFromSmarts(mcs.smartsString)
    rdDepictor.Compute2DCoords(mols[0])
    for m in mols:
        try:
            rdDepictor.GenerateDepictionMatching2DStructure(m, mols[0], refPatt=core)
        except Exception:
            rdDepictor.Compute2DCoords(m)
    return core


def _highlight_atoms(mol):
    """Atoms/colours: aromatic ring=green, any OH=red(orange), carbonyl=blue."""
    cols, atoms = {}, []
    def add(smarts, color):
        for match in mol.GetSubstructMatches(Chem.MolFromSmarts(smarts)):
            for a in match:
                atoms.append(a); cols[a] = color
    add("c", (0.62, 0.79, 0.88))             # aromatic carbons (light blue)
    add("[#6]=O", (0.65, 0.81, 0.89))        # carbonyl C
    add("[OX2H]", (0.96, 0.65, 0.51))        # hydroxyl O (orange-red)
    add("[OX1]=[#6]", (0.40, 0.55, 0.85))    # carbonyl O (blue)
    return list(set(atoms)), cols


def _mol_png(mol, legend, size=(360, 300)):
    d = rdMolDraw2D.MolDraw2DCairo(*size)
    opt = d.drawOptions()
    opt.legendFontSize = 20
    opt.bondLineWidth = 2
    hl, hlc = _highlight_atoms(mol)
    rdMolDraw2D.PrepareAndDrawMolecule(d, mol, legend=legend,
                                       highlightAtoms=hl, highlightAtomColors=hlc)
    d.FinishDrawing()
    return Image.open(io.BytesIO(d.GetDrawingText()))


# biologically accurate captions (the experimental phenotype, not the CSV role)
CAPTIONS = {
    "testosterone": "WT responder",
    "progesterone": "WT responder",
    "cortisol":     "WT non-responder\ngained by F119W; preferred by L147R",
    "estradiol":    "non-responder\n(engineering goal)",
}
CAP_COLOR = {
    "testosterone": "#1b9e77", "progesterone": "#1b9e77",
    "cortisol": "#d95f02", "estradiol": "#e7298a",
}


def fig_structures(rows, out_base):
    _aligned_2d(rows)
    n = len(rows)
    fig, axes = plt.subplots(1, n, figsize=(3.2 * n, 3.7))
    for ax, r in zip(np.atleast_1d(axes), rows):
        cap = CAPTIONS.get(r["name"], r["role"])
        img = _mol_png(r["mol"], legend="")
        ax.imshow(img); ax.axis("off")
        ax.set_title(f"{r['name']}\n{descriptors(r['mol'])['Formula']}",
                     fontsize=12, fontweight="bold")
        ax.text(0.5, -0.04, cap, transform=ax.transAxes, ha="center",
                va="top", fontsize=8.5, color=CAP_COLOR.get(r["name"], "#555"),
                fontweight="bold")
    # legend for highlight colours
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=(0.62, 0.79, 0.88), label="aromatic / carbonyl C"),
               Patch(facecolor=(0.96, 0.65, 0.51), label="hydroxyl –OH"),
               Patch(facecolor=(0.40, 0.55, 0.85), label="carbonyl =O")]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False,
               bbox_to_anchor=(0.5, -0.04), fontsize=9)
    fig.suptitle("Steroid panel: functional-group differences (core-aligned)",
                 fontsize=13, fontweight="bold", y=1.03)
    fig.subplots_adjust(bottom=0.20, top=0.86)
    for ext in ("png", "pdf"):
        fig.savefig(f"{out_base}.{ext}", bbox_inches="tight")
    plt.close(fig)


def fig_descriptor_heatmap(rows, out_base):
    keys = ["MW", "cLogP", "TPSA", "HBD", "HBA", "n_OH", "n_C=O",
            "AromRings", "FracCSP3", "RotBonds", "HeavyAtoms"]
    names = [r["name"] for r in rows]
    M = np.array([[descriptors(r["mol"])[k] for k in keys] for r in rows], float)
    # z-score each descriptor (column) for comparability
    Z = (M - M.mean(0)) / (M.std(0) + 1e-9)
    fig, ax = plt.subplots(figsize=(1.05 * len(keys) + 1.5, 0.7 * len(names) + 1.8))
    im = ax.imshow(Z, cmap="RdBu_r", aspect="auto", vmin=-1.8, vmax=1.8)
    ax.set_xticks(range(len(keys))); ax.set_xticklabels(keys, rotation=45, ha="right")
    ax.set_yticks(range(len(names))); ax.set_yticklabels(names, fontweight="bold")
    for i in range(len(names)):
        for j in range(len(keys)):
            ax.text(j, i, f"{M[i,j]:g}", ha="center", va="center", fontsize=8,
                    color="black")
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cb.set_label("z-score (per descriptor)", fontsize=9)
    ax.set_title("Physicochemical descriptors (raw values shown; colour = z-score)",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(f"{out_base}.{ext}", bbox_inches="tight")
    plt.close(fig)
    return keys, names, M


def fig_similarity(rows, out_base):
    fps = [AllChem.GetMorganFingerprintAsBitVect(r["mol"], 2, nBits=2048) for r in rows]
    names = [r["name"] for r in rows]
    n = len(rows)
    S = np.eye(n)
    for i in range(n):
        for j in range(n):
            S[i, j] = DataStructs.TanimotoSimilarity(fps[i], fps[j])
    fig, ax = plt.subplots(figsize=(0.9 * n + 2.2, 0.9 * n + 1.8))
    im = ax.imshow(S, cmap="viridis", vmin=0, vmax=1)
    ax.set_xticks(range(n)); ax.set_xticklabels(names, rotation=45, ha="right")
    ax.set_yticks(range(n)); ax.set_yticklabels(names, fontweight="bold")
    for i in range(n):
        for j in range(n):
            ax.text(j, i, f"{S[i,j]:.2f}", ha="center", va="center",
                    color="white" if S[i, j] < 0.6 else "black", fontsize=10)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Tanimoto similarity (Morgan r=2, 2048 bit)", fontsize=9)
    ax.set_title("Pairwise structural similarity", fontsize=12, fontweight="bold")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(f"{out_base}.{ext}", bbox_inches="tight")
    plt.close(fig)
    return names, S


def write_table(rows, out_csv):
    keys = ["name", "role", "Formula", "MW", "cLogP", "TPSA", "HBD", "HBA",
            "n_OH", "n_C=O", "AromRings", "FracCSP3", "RotBonds", "HeavyAtoms"]
    with open(out_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            d = descriptors(r["mol"]); d.update({"name": r["name"], "role": r["role"]})
            w.writerow({k: d[k] for k in keys})


def run(panel_csv, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    rows = load_panel(panel_csv)
    # order: target first, then responders, cortisol, estradiol last if present
    order = {"testosterone": 0, "progesterone": 1, "cortisol": 2, "estradiol": 3}
    rows.sort(key=lambda r: order.get(r["name"], 9))

    write_table(rows, os.path.join(out_dir, "descriptors.csv"))
    fig_structures(rows, os.path.join(out_dir, "fig1_structures"))
    fig_descriptor_heatmap(rows, os.path.join(out_dir, "fig2_descriptors"))
    names, S = fig_similarity(rows, os.path.join(out_dir, "fig3_similarity"))

    print(f"[cheminformatics] wrote descriptors.csv + fig1/fig2/fig3 (.png/.pdf) -> {out_dir}")
    print("\nTanimoto similarity:")
    print("         " + " ".join(f"{n[:5]:>6s}" for n in names))
    for i, n in enumerate(names):
        print(f"  {n[:7]:7s} " + " ".join(f"{S[i,j]:6.2f}" for j in range(len(names))))
    print("\nDescriptor table:")
    for r in rows:
        d = descriptors(r["mol"])
        print(f"  {r['name']:13s} {d['Formula']:9s} MW{d['MW']:6.1f} "
              f"cLogP{d['cLogP']:5.2f} TPSA{d['TPSA']:5.1f} "
              f"HBD{d['HBD']} HBA{d['HBA']} OH{d['n_OH']} C=O{d['n_C=O']} "
              f"ArRings{d['AromRings']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panel", required=True)
    ap.add_argument("--out_dir", required=True)
    args = ap.parse_args()
    run(args.panel, args.out_dir)


if __name__ == "__main__":
    main()
