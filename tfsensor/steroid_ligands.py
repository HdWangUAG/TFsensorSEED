"""Build a 3D steroid ligand panel for the AcrR specificity screen.

Adapted from AcylSEED ``fatb/acyl_ligands.py``. Where that module generated an
acyl-chain series (length-only variation), steroids are arbitrary fused-ring
molecules, so we read a ``name,smiles[,role]`` panel CSV and embed one MMFF-
optimised 3D conformer per ligand (RDKit ETKDGv3 + MMFF94), with explicit Hs.

The discriminating chemistry is deliberately subtle (estradiol's aromatic A-ring
+ phenolic 3-OH vs the decoys' 4-en-3-one A-ring), which is exactly why the
downstream selectivity scoring is a multi-model consensus, not a single docking.

CLI:
    python -m tfsensor.steroid_ligands --panel_csv data/steroid_panel.csv \
        --out_dir data/ligands
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _formula(mol) -> str:
    from rdkit.Chem import rdMolDescriptors
    return rdMolDescriptors.CalcMolFormula(mol)


def build_steroid_panel(panel_csv, out_dir=".", seed=0xF00D):
    """Build one embedded 3D SDF per ligand listed in ``panel_csv``.

    Returns ``{name: {"sdf", "smiles", "role", "formula", "heavy_atoms"}}``.
    Each SDF is a single MMFF-optimised conformer with explicit Hs.
    """
    from rdkit import Chem
    from rdkit.Chem import AllChem

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = list(csv.DictReader(open(panel_csv)))
    panel = {}
    for i, row in enumerate(rows):
        name = row["name"].strip()
        smi = row["smiles"].strip()
        role = (row.get("role") or "").strip()
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            raise ValueError(f"RDKit could not parse SMILES for {name}: {smi}")
        mol = Chem.AddHs(mol)

        params = AllChem.ETKDGv3()
        params.randomSeed = seed + i
        if AllChem.EmbedMolecule(mol, params) != 0:
            if AllChem.EmbedMolecule(mol, randomSeed=seed + i,
                                     useRandomCoords=True) != 0:
                raise RuntimeError(f"3D embedding failed for {name}")
        AllChem.MMFFOptimizeMolecule(mol)

        mol.SetProp("_Name", name)
        sdf = out_dir / f"{name}.sdf"
        writer = Chem.SDWriter(str(sdf))
        writer.write(mol)
        writer.close()

        panel[name] = {
            "sdf": str(sdf),
            "smiles": smi,
            "role": role,
            "formula": _formula(mol),
            "heavy_atoms": mol.GetNumHeavyAtoms(),
        }
    return panel


def main():
    ap = argparse.ArgumentParser(description="Build a 3D steroid ligand panel.")
    ap.add_argument("--panel_csv", required=True,
                    help="CSV with name,smiles[,role] columns")
    ap.add_argument("--out_dir", required=True)
    args = ap.parse_args()

    panel = build_steroid_panel(args.panel_csv, args.out_dir)
    print(json.dumps(panel, indent=2))
    print(f"OK: built {len(panel)} ligands in {args.out_dir}")


if __name__ == "__main__":
    main()
