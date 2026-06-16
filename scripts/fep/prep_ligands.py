#!/usr/bin/env python3
"""Per-ligand FEP prep: from each WT holo pose, extract (a) protein_only.pdb and
(b) the in-pocket ligand, assign correct bond orders/H from SMILES, and GAFF2-
parameterise via acpype. Run with an RDKit-capable python; acpype is invoked in
the `fep` conda env.

  app_python prep_ligands.py --out prep --ligands testosterone,progesterone,cortisol,estradiol
"""
import argparse, os, subprocess, sys

PANEL = {}  # name -> smiles, filled from data/steroid_panel.csv
REPO = os.path.expanduser("~/TFsensorSEED")
HOLO = (REPO + "/results/stage1_wt_validation/boltz/seed1/boltz_results_inputs/"
        "predictions/wt_{lig}/wt_{lig}_model_0.pdb")


def load_panel():
    import csv
    with open(REPO + "/data/steroid_panel.csv") as fh:
        for r in csv.DictReader(fh):
            PANEL[r["name"]] = r["smiles"]


def split_pdb(holo):
    """Return (protein_lines[A/B ATOM], ligand_lines[HETATM chain L])."""
    prot, lig = [], []
    for ln in open(holo):
        if ln.startswith("ATOM") and ln[21] in ("A", "B"):
            prot.append(ln)
        elif ln.startswith("HETATM") and ln[21] == "L":
            lig.append(ln)
    return prot, lig


def prep_one(lig, smiles, out):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    holo = HOLO.format(lig=lig)
    od = os.path.join(out, lig); os.makedirs(od, exist_ok=True)
    prot_lines, lig_lines = split_pdb(holo)
    assert prot_lines and lig_lines, f"{lig}: empty protein/ligand from {holo}"

    # (a) protein_only.pdb
    with open(os.path.join(od, "protein_only.pdb"), "w") as fh:
        fh.writelines(prot_lines); fh.write("END\n")

    # (b) ligand: PDB block -> RDKit mol (proximity bonds) -> assign orders from SMILES
    block = "".join(lig_lines) + "END\n"
    raw = Chem.MolFromPDBBlock(block, removeHs=True, proximityBonding=True, sanitize=False)
    assert raw is not None, f"{lig}: RDKit could not read ligand block"
    tmpl = Chem.MolFromSmiles(smiles)
    assert tmpl is not None, f"{lig}: bad SMILES"
    mol = AllChem.AssignBondOrdersFromTemplate(tmpl, raw)
    mol = Chem.AddHs(mol, addCoords=True)          # protonate, keep heavy-atom coords
    Chem.SanitizeMol(mol)
    for a in mol.GetAtoms():                        # uniform residue name LIG
        ri = a.GetPDBResidueInfo()
        if ri: ri.SetResidueName("LIG")
    molfile = os.path.join(od, f"{lig}.mol")
    Chem.MolToMolFile(mol, molfile)
    Chem.MolToPDBFile(mol, os.path.join(od, f"{lig}_lig.pdb"))
    net = Chem.GetFormalCharge(mol)
    print(f"[prep] {lig}: protein {len(prot_lines)} atoms, ligand {mol.GetNumAtoms()} "
          f"atoms (formal charge {net}); SMILES OK", flush=True)

    # (c) acpype GAFF2/AM1-BCC in the fep env (preserves input coords)
    cmd = ["conda", "run", "-n", "fep", "acpype", "-i", os.path.abspath(molfile),
           "-b", lig, "-n", str(net), "-a", "gaff2", "-c", "bcc", "-o", "gmx"]
    r = subprocess.run(cmd, cwd=od, capture_output=True, text=True)
    itp = os.path.join(od, f"{lig}.acpype", f"{lig}_GMX.itp")
    if not os.path.exists(itp):
        print(f"[prep][FAIL] {lig} acpype:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
        return False
    print(f"[prep] {lig}: acpype OK -> {itp}", flush=True)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="prep")
    ap.add_argument("--ligands", default="testosterone,progesterone,cortisol,estradiol")
    a = ap.parse_args()
    load_panel()
    os.makedirs(a.out, exist_ok=True)
    ok = []
    for lig in [x.strip() for x in a.ligands.split(",") if x.strip()]:
        ok.append((lig, prep_one(lig, PANEL[lig], a.out)))
    print("\n=== prep summary ===")
    for lig, s in ok:
        print(f"  {lig}: {'OK' if s else 'FAILED'}")
    sys.exit(0 if all(s for _, s in ok) else 1)


if __name__ == "__main__":
    main()
