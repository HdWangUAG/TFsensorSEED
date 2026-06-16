"""Prepare AcrR receptor metadata for the prediction stages.

Pure-Python PDB parsing (no BioPython — the pyrosetta/worker env historically
lacks Bio; this mirrors the LC-SEED golden rule). Produces:

1. ``AcrR_dimer.fasta`` — chain A and chain B one-letter sequences (for Boltz /
   Protenix holo inputs).
2. ``resmap.json`` — per-chain PDB-resSeq <-> sequential predictor numbering
   (Boltz/Protenix renumber each chain 1..N). Keyed by chain.
3. A 4.5 A contact scan of the bound STR ligand -> the pocket residue set
   (chain + resSeq), to confirm/replace the draft pocket list in the plan.

CLI:
    python -m tfsensor.prep_receptor --holo data/AcrR_STR_001.pdb \
        --lig_resname STR --out_dir data
"""
from __future__ import annotations

import argparse
import json
import math
import os

_THREE2ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q",
    "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V", "MSE": "M", "SEC": "U",
}


def _xyz(line):
    return (float(line[30:38]), float(line[38:46]), float(line[46:54]))


def parse_pdb(pdb_path):
    """Return (chains, ligand_atoms).

    chains[chain] = ordered list of (resSeq, resName, {atomName: xyz})
    ligand_atoms = list of (chain, resName, atomName, xyz) for HETATM (no water/H)
    """
    chains = {}
    seen = {}                       # (chain, resSeq) -> residue dict
    ligand_atoms = []
    for l in open(pdb_path):
        rec = l[:6].strip()
        if rec == "ATOM":
            ch = l[21]
            resseq = int(l[22:26])
            resname = l[17:20].strip()
            atom = l[12:16].strip()
            key = (ch, resseq)
            if key not in seen:
                d = {"resSeq": resseq, "resName": resname, "atoms": {}}
                seen[key] = d
                chains.setdefault(ch, []).append(d)
            seen[key]["atoms"][atom] = _xyz(l)
        elif rec == "HETATM":
            resname = l[17:20].strip()
            if resname in ("HOH", "WAT"):
                continue
            el = (l[76:78].strip() or l[12:16].strip()[0]).upper()
            if el == "H":
                continue
            ligand_atoms.append((l[21], resname, l[12:16].strip(), _xyz(l)))
    return chains, ligand_atoms


def write_fasta(chains, out_fasta, name="AcrR"):
    lines = []
    seqs = {}
    for ch in sorted(chains):
        seq = "".join(_THREE2ONE.get(r["resName"], "X") for r in chains[ch])
        seqs[ch] = seq
        lines.append(f">{name}_chain{ch}")
        for i in range(0, len(seq), 60):
            lines.append(seq[i:i + 60])
    open(out_fasta, "w").write("\n".join(lines) + "\n")
    return seqs


def build_resmap(chains):
    """Per-chain PDB-resSeq <-> predictor index (1..N in chain order)."""
    resmap = {}
    for ch in sorted(chains):
        pdb2idx, idx2pdb = {}, {}
        for i, r in enumerate(chains[ch], start=1):
            pdb2idx[r["resSeq"]] = i
            idx2pdb[i] = r["resSeq"]
        resmap[ch] = {"pdb2idx": pdb2idx, "idx2pdb": idx2pdb}
    return resmap


def pocket_scan(chains, ligand_atoms, cutoff=4.5):
    """Protein residues with any heavy atom within ``cutoff`` of any ligand atom."""
    lig = [a[3] for a in ligand_atoms]
    hits = []
    for ch in sorted(chains):
        for r in chains[ch]:
            mind = math.inf
            for axyz in r["atoms"].values():
                for lxyz in lig:
                    d = math.dist(axyz, lxyz)
                    if d < mind:
                        mind = d
            if mind < cutoff:
                hits.append({"chain": ch, "resSeq": r["resSeq"],
                             "resName": r["resName"], "min_dist": round(mind, 2)})
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--holo", required=True, help="holo PDB (protein + ligand)")
    ap.add_argument("--lig_resname", default="STR")
    ap.add_argument("--cutoff", type=float, default=4.5)
    ap.add_argument("--out_dir", default="data")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    chains, ligand_atoms = parse_pdb(args.holo)
    ligand_atoms = [a for a in ligand_atoms if a[1] == args.lig_resname]

    seqs = write_fasta(chains, os.path.join(args.out_dir, "AcrR_dimer.fasta"))
    resmap = build_resmap(chains)
    json.dump(resmap, open(os.path.join(args.out_dir, "resmap.json"), "w"), indent=2)
    hits = pocket_scan(chains, ligand_atoms, args.cutoff)
    json.dump(hits, open(os.path.join(args.out_dir, "pocket_residues.json"), "w"),
              indent=2)

    print("Chains + lengths:")
    for ch, s in seqs.items():
        print(f"  chain {ch}: {len(s)} residues")
    ident = len(set(seqs.values())) == 1
    print(f"  chains identical: {ident}")
    print(f"\nLigand {args.lig_resname}: {len(ligand_atoms)} heavy atoms")
    print(f"\nPocket residues within {args.cutoff} A of {args.lig_resname} "
          f"({len(hits)} hits):")
    by_chain = {}
    for h in hits:
        by_chain.setdefault(h["chain"], []).append(h)
    for ch in sorted(by_chain):
        rs = ", ".join(f"{h['resName']}{h['resSeq']}({h['min_dist']})"
                       for h in sorted(by_chain[ch], key=lambda x: x["resSeq"]))
        print(f"  chain {ch}: {rs}")


if __name__ == "__main__":
    main()
