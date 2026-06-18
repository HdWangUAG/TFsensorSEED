"""Template-based steroid posing by rigid gonane-core superposition.

Blind flexible docking of steroids is unreliable: the rigid gonane core lets them
settle upside-down/backwards in permissive pockets → garbage contact features. We
avoid docking entirely. Because every steroid shares the gonane core, we place a
query steroid by **superposing its core onto a reference steroid whose pose in the
pocket is known** (a crystal ligand from LC-SEED, or the AcrR STR reference). The
core orientation is then correct by construction; only the substituents differ.

Pipeline per query:
  1. embed a 3D conformer (ETKDG + MMFF),
  2. find the shared core via ring-only MCS with the reference (≈ the gonane nucleus),
  3. rigidly align the query onto the reference over the matched core atoms,
  4. FILTER: reject if the matched core is too small (not a genuine steroid match)
     or the core alignment RMSD is high (shouldn't happen for a rigid core — a red
     flag for a bad/promiscuous match).

Returns the posed query (now sitting in the reference's frame, i.e. the pocket)
plus QC numbers. Substituent relaxation (MMFF, core fixed) is an optional refine
step left for the contact stage. Pure RDKit; no GPU, no docking.
"""
from __future__ import annotations

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, rdFMCS, rdMolAlign

from tfsensor.ml.data.steroid_filter import find_gonane_nucleus

RDLogger.DisableLog("rdApp.*")

# QC thresholds: gonane nucleus = 17 carbons; require most of it to match well.
MIN_CORE_ATOMS = 15
MAX_CORE_RMSD = 1.0      # Å; rigid-core superposition should be near-perfect


def embed_3d(smiles, seed=0xF00D):
    """SMILES -> 3D mol with Hs (ETKDGv3 + MMFF). None on failure."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = seed
    if AllChem.EmbedMolecule(mol, params) != 0:
        return None
    try:
        AllChem.MMFFOptimizeMolecule(mol)
    except Exception:
        pass
    return mol


def _core_match(query, reference):
    """Atom correspondence over the RIGID GONANE NUCLEUS only (query_idx, ref_idx).

    Aligning over the full MCS would drag in flexible substituents/Hs and inflate
    the RMSD. We take the ring-only MCS for the correspondence but then keep only
    pairs where BOTH atoms belong to their molecule's gonane nucleus — so the
    superposition is driven purely by the rigid 4-ring core. CompareAny bonds let
    an aromatic A-ring (estradiol) match an enone A-ring (testosterone).
    """
    mcs = rdFMCS.FindMCS([query, reference], ringMatchesRingOnly=True,
                         completeRingsOnly=True,
                         atomCompare=rdFMCS.AtomCompare.CompareElements,
                         bondCompare=rdFMCS.BondCompare.CompareAny, timeout=5)
    if mcs.numAtoms == 0:
        return None, 0
    core = Chem.MolFromSmarts(mcs.smartsString)
    qm = query.GetSubstructMatch(core)
    rm = reference.GetSubstructMatch(core)
    if not qm or not rm or len(qm) != len(rm):
        return None, 0
    q_nuc = set(find_gonane_nucleus(query) or ())
    r_nuc = set(find_gonane_nucleus(reference) or ())
    core_map = [(qi, ri) for qi, ri in zip(qm, rm)
                if qi in q_nuc and ri in r_nuc]
    return core_map, len(core_map)


def pose_by_core(query_smiles, reference_mol, seed=0xF00D,
                 min_core=MIN_CORE_ATOMS, max_rmsd=MAX_CORE_RMSD):
    """Place `query_smiles` into `reference_mol`'s frame by core superposition.

    reference_mol: an RDKit mol WITH a 3D conformer = the known steroid pose in
    the pocket. Returns dict {mol, core_rmsd, core_atoms, accepted, reason} or a
    rejection dict (accepted=False).
    """
    q = embed_3d(query_smiles, seed=seed)
    if q is None:
        return {"accepted": False, "reason": "embed_failed"}
    atom_map, n_core = _core_match(q, reference_mol)
    if atom_map is None or n_core < min_core:
        return {"accepted": False, "reason": f"core_too_small({n_core})",
                "core_atoms": n_core}
    # rigid superposition of query onto reference over the core atoms
    rmsd = rdMolAlign.AlignMol(q, reference_mol, atomMap=atom_map)
    accepted = rmsd <= max_rmsd
    return {
        "mol": q,
        "core_rmsd": round(float(rmsd), 3),
        "core_atoms": n_core,
        "accepted": accepted,
        "reason": "ok" if accepted else f"core_rmsd_high({rmsd:.2f})",
    }


def reference_from_smiles(smiles, seed=0xF00D):
    """Convenience: build a 3D reference mol from SMILES (stand-in for a crystal)."""
    return embed_3d(smiles, seed=seed)
