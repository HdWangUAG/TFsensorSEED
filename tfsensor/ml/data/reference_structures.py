"""Canonical AGONIST reference structures per nuclear receptor.

Antagonist-bound NR structures have a displaced Helix 12 and a distorted pocket,
so they are the wrong template for posing. We therefore select, per receptor, the
**highest-resolution crystal bound to its natural (agonist) ligand** — which fixes
the active-state pocket by construction:

    AR  -> DHT / testosterone     ER  -> estradiol        GR -> cortisol / dexamethasone
    PR  -> progesterone           MR  -> aldosterone

Selection = RCSB combined query (receptor UniProt + ligand comp id) sorted by
resolution. Then we fetch the PDB, build a clean reference ligand pose (3D coords
from the crystal + bond orders from the CCD SMILES template, the same trick as
tfsensor.physics_score), and extract the 8 Å pocket. These references are the
templates onto which ChEMBL ligands are core-aligned (tfsensor.ml.features.template_pose).

Run (needs network — RCSB):
    ~/LC-Seed/envs/app/.venv/bin/python -m tfsensor.ml.data.reference_structures --build-all
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

from tfsensor.ml.data.pocket_extract import extract_pocket

RDLogger.DisableLog("rdApp.*")

REFS_DIR = "data/ml/refs"
SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"

# receptor -> (UniProt accession, [natural ligand CCD codes, in preference order])
REFERENCE_SPEC = {
    "AR":   ("P10275", ["DHT", "TES"]),
    "ESR1": ("P03372", ["EST"]),
    "ESR2": ("Q92731", ["EST"]),
    "GR":   ("P04150", ["HCY", "DEX"]),   # cortisol, then dexamethasone
    "PR":   ("P06401", ["STR"]),          # STR = progesterone
    "MR":   ("P08235", ["AS4"]),          # AS4 = aldosterone
}


def _search(query):
    req = urllib.request.Request(SEARCH_URL, data=json.dumps(query).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def _combined_query(uniprot, comp_id):
    return {"query": {"type": "group", "logical_operator": "and", "nodes": [
        {"type": "terminal", "service": "text", "parameters": {
            "attribute": "rcsb_polymer_entity_container_identifiers."
                         "reference_sequence_identifiers.database_accession",
            "operator": "exact_match", "value": uniprot}},
        {"type": "terminal", "service": "text", "parameters": {
            "attribute": "rcsb_nonpolymer_entity_container_identifiers."
                         "nonpolymer_comp_id",
            "operator": "exact_match", "value": comp_id}}]},
        "return_type": "entry",
        "request_options": {"sort": [{"sort_by": "rcsb_entry_info.resolution_combined",
                                      "direction": "asc"}],
                            "paginate": {"rows": 3}}}


def _resolution(pdb):
    try:
        d = json.load(urllib.request.urlopen(
            f"https://data.rcsb.org/rest/v1/core/entry/{pdb}", timeout=30))
        r = d.get("rcsb_entry_info", {}).get("resolution_combined")
        return r[0] if r else None
    except Exception:
        return None


def select_reference(receptor):
    """Highest-resolution agonist (natural-ligand) crystal for a receptor."""
    uniprot, ligands = REFERENCE_SPEC[receptor]
    for comp in ligands:
        res = _search(_combined_query(uniprot, comp))
        ids = [x["identifier"] for x in res.get("result_set", [])]
        if ids:
            pdb = ids[0].lower()
            return {"receptor": receptor, "uniprot": uniprot, "ligand_code": comp,
                    "pdb": pdb, "resolution": _resolution(pdb),
                    "n_candidates": res.get("total_count")}
    return None


def fetch_pdb(pdb, out_dir=REFS_DIR):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{pdb}.pdb")
    if not os.path.exists(path):
        urllib.request.urlretrieve(f"https://files.rcsb.org/download/{pdb}.pdb", path)
    return path


def _first_ligand_instance(pdb_path, comp):
    """HETATM lines of the first (chain,resSeq) instance of comp; and its chain."""
    by_inst = {}
    for l in open(pdb_path):
        if l.startswith("HETATM") and l[17:20].strip() == comp:
            el = (l[76:78].strip() or l[12:16].strip()[0]).upper()
            if el == "H":
                continue
            key = (l[21], l[22:26])
            by_inst.setdefault(key, []).append(l)
    if not by_inst:
        return None, None
    (chain, _), lines = next(iter(by_inst.items()))
    return lines, chain


def build_reference_ligand(pdb_path, comp, smiles, out_sdf):
    """Clean 3D reference ligand: crystal coords + bond orders from CCD SMILES."""
    lig_lines, chain = _first_ligand_instance(pdb_path, comp)
    if not lig_lines:
        raise ValueError(f"no {comp} HETATM in {pdb_path}")
    tmp = out_sdf + ".lig.pdb"
    with open(tmp, "w") as fh:
        fh.writelines(lig_lines)
        fh.write("END\n")
    raw = Chem.MolFromPDBFile(tmp, removeHs=True, sanitize=False)
    if raw is None:
        raise RuntimeError(f"RDKit could not read {comp} from {pdb_path}")
    template = Chem.MolFromSmiles(smiles)
    mol = AllChem.AssignBondOrdersFromTemplate(template, raw)
    Chem.MolToMolFile(mol, out_sdf)
    return out_sdf, chain, mol.GetNumHeavyAtoms()


def build_reference(receptor, ccd_smiles_path="data/ml/cache/ccd_smiles.json",
                    out_dir=REFS_DIR):
    """Select + fetch + build (ligand SDF, pocket JSON) for one receptor."""
    sel = select_reference(receptor)
    if not sel:
        return {"receptor": receptor, "error": "no agonist reference found"}
    ccd = json.load(open(ccd_smiles_path))
    smiles = ccd.get(sel["ligand_code"])
    pdb_path = fetch_pdb(sel["pdb"], out_dir)
    sdf = os.path.join(out_dir, f"{receptor}_{sel['pdb']}_{sel['ligand_code']}.sdf")
    try:
        sdf, chain, n_heavy = build_reference_ligand(pdb_path, sel["ligand_code"],
                                                     smiles, sdf)
    except Exception as e:
        return {**sel, "error": f"ligand build failed: {e}"}
    pocket = extract_pocket(pdb_path, lig_resname=sel["ligand_code"],
                            lig_chain=chain, cutoff=8.0)
    pocket_json = os.path.join(out_dir, f"{receptor}_pocket.json")
    json.dump(pocket, open(pocket_json, "w"))
    return {**sel, "ligand_sdf": sdf, "ligand_chain": chain,
            "ligand_heavy_atoms": n_heavy, "pocket_json": pocket_json,
            "pocket_residues": len(pocket["residues"])}


def _main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build-all", action="store_true")
    ap.add_argument("--receptor", default=None)
    ap.add_argument("--out_dir", default=REFS_DIR)
    args = ap.parse_args()
    receptors = [args.receptor] if args.receptor else list(REFERENCE_SPEC)
    if not (args.build_all or args.receptor):
        ap.error("use --build-all or --receptor")
    summary = {}
    for rec in receptors:
        info = build_reference(rec, out_dir=args.out_dir)
        summary[rec] = info
        if "error" in info:
            print(f"{rec:5s} ERROR: {info['error']}")
        else:
            print(f"{rec:5s} {info['pdb']} {info['ligand_code']} "
                  f"({info['resolution']}Å)  lig_heavy={info['ligand_heavy_atoms']} "
                  f"pocket={info['pocket_residues']} res")
    json.dump(summary, open(os.path.join(args.out_dir, "reference_selection.json"), "w"),
              indent=2)


if __name__ == "__main__":
    _main()
