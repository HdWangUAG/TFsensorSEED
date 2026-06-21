"""Tool registry — real functions agents can call (Phase 3 tool-calling).

Each tool is a Python function with a name, description and JSON-schema params.
The first batch is RDKit cheminformatics (real numbers for the ligand side of the
project). Add PyRosetta / ESM2 / XGBoost tools here the same way later.
"""
from __future__ import annotations

# A few project-relevant ligands so agents can pass a name instead of SMILES.
KNOWN_SMILES = {
    "estradiol": "C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc43)[C@@H]1CC[C@@H]2O",
    "testosterone": "C[C@]12CC[C@H]3[C@@H](CCC4=CC(=O)CC[C@]34C)[C@@H]1CC[C@@H]2O",
    "progesterone": "CC(=O)[C@H]1CC[C@H]2[C@@H]3CCC4=CC(=O)CC[C@]4(C)[C@H]3CC[C@]12C",
    "cortisol": "C[C@]12C[C@H](O)[C@H]3[C@@H](CCC4=CC(=O)CC[C@]34C)[C@@H]1CC[C@@]2(O)C(=O)CO",
}


def _mol(smiles_or_name):
    from rdkit import Chem
    s = KNOWN_SMILES.get(str(smiles_or_name).strip().lower(), smiles_or_name)
    return Chem.MolFromSmiles(s), s


def ligand_descriptors(ligand):
    """Physicochemical descriptors for a ligand (name or SMILES)."""
    from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors
    mol, smi = _mol(ligand)
    if mol is None:
        return {"error": f"could not parse {ligand!r}"}
    return {
        "input": ligand, "smiles": smi,
        "MW": round(Descriptors.MolWt(mol), 2),
        "logP": round(Crippen.MolLogP(mol), 2),
        "HBD": rdMolDescriptors.CalcNumHBD(mol),
        "HBA": rdMolDescriptors.CalcNumHBA(mol),
        "TPSA": round(rdMolDescriptors.CalcTPSA(mol), 1),
        "rings": rdMolDescriptors.CalcNumRings(mol),
        "aromatic_rings": rdMolDescriptors.CalcNumAromaticRings(mol),
        "rot_bonds": rdMolDescriptors.CalcNumRotatableBonds(mol),
    }


def ligand_similarity(ligand_a, ligand_b):
    """Tanimoto similarity (Morgan r2) between two ligands (names or SMILES)."""
    from rdkit.Chem import AllChem, DataStructs
    ma, _ = _mol(ligand_a)
    mb, _ = _mol(ligand_b)
    if ma is None or mb is None:
        return {"error": "could not parse one of the ligands"}
    fa = AllChem.GetMorganFingerprintAsBitVect(ma, 2, 2048)
    fb = AllChem.GetMorganFingerprintAsBitVect(mb, 2, 2048)
    return {"ligand_a": ligand_a, "ligand_b": ligand_b,
            "tanimoto": round(DataStructs.TanimotoSimilarity(fa, fb), 3)}


REGISTRY = {
    "ligand_descriptors": {
        "fn": ligand_descriptors,
        "description": "Compute physicochemical descriptors (MW, logP, H-bond "
                       "donors/acceptors, TPSA, rings, aromatic rings, rotatable "
                       "bonds) for a ligand given a name or SMILES.",
        "parameters": {
            "type": "object",
            "properties": {"ligand": {"type": "string",
                           "description": "ligand name (e.g. estradiol) or SMILES"}},
            "required": ["ligand"]},
    },
    "ligand_similarity": {
        "fn": ligand_similarity,
        "description": "Tanimoto (Morgan) similarity between two ligands "
                       "(names or SMILES).",
        "parameters": {
            "type": "object",
            "properties": {
                "ligand_a": {"type": "string"},
                "ligand_b": {"type": "string"}},
            "required": ["ligand_a", "ligand_b"]},
    },
}


def openai_schemas(names=None):
    """Tool list in OpenAI function-calling format."""
    names = names or list(REGISTRY)
    return [{"type": "function", "function": {
                "name": n, "description": REGISTRY[n]["description"],
                "parameters": REGISTRY[n]["parameters"]}}
            for n in names if n in REGISTRY]
