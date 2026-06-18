"""Contacts from a core-aligned steroid pose → interpretable fingerprint.

Closes the contact bridge: given a steroid posed by rigid-core superposition onto
a receptor's agonist reference (tfsensor.ml.features.template_pose) and that
reference's pocket residues, classify residue↔ligand contacts into the same four
PLIP-style types LC-SEED uses (hbond / hydrophobic / pistacking / saltbridge), via
a transparent distance+chemistry heuristic. The result feeds
contacts_fingerprint, so a trained model's weights map back to specific
residue↔ligand contacts (the mandated interpretability).

Heuristic (independent flags per pocket residue, PLIP-style):
  hbond        polar ligand atom (N/O) .. polar residue atom (N/O)        ≤ 3.5 Å
  saltbridge   charged residue atom (Asp/Glu O⁻, Lys/Arg N⁺) .. ligand O  ≤ 4.0 Å
  pistacking   aromatic residue ring atom .. aromatic ligand atom         ≤ 5.0 Å
  hydrophobic  carbon .. carbon                                            ≤ 4.5 Å
"""
from __future__ import annotations

import json
import math
import os

from rdkit import Chem, RDLogger

from tfsensor.prep_receptor import parse_pdb
from tfsensor.ml.features.template_pose import pose_by_core
from tfsensor.ml.features.contacts_fingerprint import fingerprint_vector, top_contacts

RDLogger.DisableLog("rdApp.*")

HBOND, SALT, PI, HPHOB = 3.5, 4.0, 5.0, 4.5
_AROMATIC_RES = {"PHE", "TYR", "TRP", "HIS"}
_CHARGED_ATOMS = {  # residue -> charged sidechain atom names
    "ASP": {"OD1", "OD2"}, "GLU": {"OE1", "OE2"},
    "LYS": {"NZ"}, "ARG": {"NH1", "NH2", "NE"},
}
_RES_AROM_ATOMS = {  # ring atoms used as a crude aromatic centroid
    "PHE": {"CG", "CD1", "CD2", "CE1", "CE2", "CZ"},
    "TYR": {"CG", "CD1", "CD2", "CE1", "CE2", "CZ"},
    "TRP": {"CG", "CD1", "CD2", "NE1", "CE2", "CE3", "CZ2", "CZ3", "CH2"},
    "HIS": {"CG", "ND1", "CD2", "CE1", "NE2"},
}


def _dist(a, b):
    return math.dist(a, b)


def ligand_heavy_atoms(mol):
    """[(element, (x,y,z), is_aromatic)] for heavy atoms of an RDKit conformer."""
    conf = mol.GetConformer()
    out = []
    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() <= 1:
            continue
        p = conf.GetAtomPosition(atom.GetIdx())
        out.append((atom.GetSymbol().upper(), (p.x, p.y, p.z), atom.GetIsAromatic()))
    return out


def pocket_residue_atoms(ref_pdb, pocket_json):
    """Pocket residues with all heavy-atom coords, from the reference PDB."""
    want = {(r["chain"], r["resSeq"]) for r in json.load(open(pocket_json))["residues"]}
    chains, _ = parse_pdb(ref_pdb)
    residues = []
    for ch, reslist in chains.items():
        for r in reslist:
            if (ch, r["resSeq"]) in want:
                residues.append((ch, r["resSeq"], r["resName"], r["atoms"]))
    return residues


def compute_contacts(mol, residues):
    """Return the LC-SEED-style contact dict for a posed ligand vs pocket residues."""
    lig = ligand_heavy_atoms(mol)
    out = {"hbond": [], "hydrophobic": [], "pistacking": [], "saltbridge": []}
    for ch, resseq, resname, atoms in residues:
        tag = f"{resname}:{resseq}"
        flags = set()
        charged = _CHARGED_ATOMS.get(resname, set())
        arom_atoms = _RES_AROM_ATOMS.get(resname, set())
        for aname, axyz in atoms.items():
            r_el = aname[0]
            r_polar = r_el in ("N", "O")
            for l_el, lxyz, l_arom in lig:
                d = _dist(axyz, lxyz)
                if d > 5.2:
                    continue
                l_polar = l_el in ("N", "O")
                if r_polar and l_polar and d <= HBOND:
                    flags.add("hbond")
                if aname in charged and l_polar and d <= SALT:
                    flags.add("saltbridge")
                if aname in arom_atoms and l_arom and d <= PI:
                    flags.add("pistacking")
                if r_el == "C" and l_el == "C" and d <= HPHOB:
                    flags.add("hydrophobic")
        for f in flags:
            out[f].append(tag)
    return out


def load_reference_assets(reference_sdf, ref_pdb, pocket_json):
    """Load (ref_mol, residues) ONCE per receptor — reuse across many ligands."""
    ref_mol = next(iter(Chem.SDMolSupplier(reference_sdf, removeHs=False)), None)
    if ref_mol is None:
        raise ValueError(f"could not load reference {reference_sdf}")
    residues = pocket_residue_atoms(ref_pdb, pocket_json)
    return ref_mol, residues


def featurize_loaded(smiles, ref_mol, residues, seed=0xF00D):
    """Pose + contact features using pre-loaded reference assets (fast path)."""
    posed = pose_by_core(smiles, ref_mol, seed=seed)
    if not posed.get("accepted"):
        return {"accepted": False, "reason": posed.get("reason"),
                "core_rmsd": posed.get("core_rmsd")}
    contacts = compute_contacts(posed["mol"], residues)
    return {
        "accepted": True,
        "core_rmsd": posed["core_rmsd"],
        "contacts": contacts,
        "fingerprint": fingerprint_vector(contacts),
        "top": top_contacts(contacts, k=6),
    }


def featurize_ligand(smiles, reference_sdf, ref_pdb, pocket_json, seed=0xF00D):
    """Convenience: load reference assets then featurize one ligand."""
    ref_mol, residues = load_reference_assets(reference_sdf, ref_pdb, pocket_json)
    return featurize_loaded(smiles, ref_mol, residues, seed=seed)


def load_references(sel_json="data/ml/refs/reference_selection.json"):
    """{receptor: {ligand_sdf, ref_pdb, pocket_json}} from the selection summary."""
    sel = json.load(open(sel_json))
    refs = {}
    for rec, info in sel.items():
        if "error" in info:
            continue
        refs[rec] = {
            "ligand_sdf": info["ligand_sdf"],
            "ref_pdb": os.path.join("data/ml/refs", f"{info['pdb']}.pdb"),
            "pocket_json": info["pocket_json"],
        }
    return refs


def _main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--demo", action="store_true",
                    help="pose the AcrR panel onto the AR reference and show contacts")
    args = ap.parse_args()
    if args.demo:
        refs = load_references()
        ar = refs["AR"]
        panel = {
            "testosterone": "C[C@]12CC[C@H]3[C@@H](CCC4=CC(=O)CC[C@]34C)[C@@H]1CC[C@@H]2O",
            "DHT": "C[C@]12CC[C@H]3[C@@H](CC[C@H]4CC(=O)CC[C@]34C)[C@@H]1CC[C@@H]2O",
            "cortisol": "C[C@]12C[C@H](O)[C@H]3[C@@H](CCC4=CC(=O)CC[C@]34C)[C@@H]1CC[C@]2(O)C(=O)CO",
        }
        for name, smi in panel.items():
            r = featurize_ligand(smi, ar["ligand_sdf"], ar["ref_pdb"], ar["pocket_json"])
            if r["accepted"]:
                print(f"{name:14s} rmsd={r['core_rmsd']}  top={r['top']}")
            else:
                print(f"{name:14s} REJECTED ({r['reason']})")


if __name__ == "__main__":
    _main()
