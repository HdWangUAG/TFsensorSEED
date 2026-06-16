"""Build Boltz-2 holo YAMLs for the AcrR homodimer + a steroid panel.

Adapted from AcylSEED ``fatb/boltz_holo_inputs.py``. Differences for AcrR:
  * AcrR is a HOMODIMER -> two identical ``protein`` blocks (chains A and B).
  * Steroids have NO thioester / catalytic anchor -> NO ``constraints`` block
    (the whole thioester-atom-naming machinery is dropped).
  * The affinity head is requested (``properties: affinity: binder: L``) so Boltz
    emits ``affinity_probability_binary`` (the validated selectivity metric).

Optional point mutations (1-based predictor numbering, applied to BOTH chains to
keep the homodimer symmetric) let you build mutant panels later.

CLI:
    python -m tfsensor.boltz_holo_inputs --seq_fasta data/AcrR_dimer.fasta \
        --panel_csv data/steroid_panel.csv --out_dir results/stage1_wt_validation/boltz/inputs \
        --prefix wt
"""
from __future__ import annotations

import argparse
import csv
import os


def _read_first_chain(fasta_path):
    """Return the first sequence in a FASTA (chains are identical for AcrR)."""
    seq, started = [], False
    for line in open(fasta_path):
        if line.startswith(">"):
            if started:
                break
            started = True
            continue
        if started:
            seq.append(line.strip())
    return "".join(seq)


def _apply_mutations(seq, mutations):
    """mutations: list of 'pos:AA' (1-based). Returns mutated seq."""
    if not mutations:
        return seq
    s = list(seq)
    for m in mutations:
        pos, aa = m.split(":")
        pos = int(pos)
        assert 1 <= pos <= len(s), f"mutate pos {pos} out of range 1..{len(s)}"
        s[pos - 1] = aa
    return "".join(s)


def build_holo_yaml(out_path, sequence, smiles, *, chains=("A", "B"),
                    binder_id="L", with_affinity=True):
    """Write a Boltz-2 YAML: N identical protein chains + 1 ligand + affinity.

    No constraints (steroids have no catalytic anchor). ``chains`` is the tuple of
    protein chain IDs (("A","B") for the AcrR homodimer; ("A",) for a monomer).
    """
    lines = ["version: 1", "sequences:"]
    for ch in chains:
        lines += [
            "  - protein:",
            f"      id: {ch}",
            f"      sequence: {sequence}",
        ]
    # AcrR homodimer has one effector pocket per monomer -> one ligand per protein chain.
    # Use SINGLE-character chain IDs (PDB chain column is 1 char; "L1"/"L2" overflow it and
    # corrupt the output so viewers/parsers see a "broken" ligand). Pick letters not used by
    # the protein chains.
    _pool = [c for c in "LMNOPQRSTUVWXYZ" if c not in chains]
    lig_ids = [binder_id] if len(chains) == 1 else _pool[:len(chains)]
    for lid in lig_ids:
        lines += ["  - ligand:", f"      id: {lid}", f"      smiles: '{smiles}'"]
    # Boltz cannot compute affinity with multiple copies of the same ligand, so the
    # affinity head is only requested for the single-ligand case (2-ligand = structure only).
    if with_affinity and len(lig_ids) == 1:
        lines += ["properties:", "  - affinity:", f"      binder: {lig_ids[0]}"]
    with open(out_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return out_path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seq_fasta", required=True, help="AcrR dimer FASTA")
    ap.add_argument("--panel_csv", default=None, help="name,smiles[,role] panel (holo only)")
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--prefix", default="wt", help="output name prefix, e.g. wt / t137g")
    ap.add_argument("--chains", default="A,B", help="protein chain ids (homodimer=A,B)")
    ap.add_argument("--mutate", default=None,
                    help="comma-sep pos:AA (1-based), applied to ALL chains")
    ap.add_argument("--apo", action="store_true",
                    help="build a single APO YAML (protein chains only, no ligand) "
                         "named <prefix>_apo.yaml; ignores --panel_csv")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    chains = tuple(c.strip() for c in args.chains.split(","))
    seq = _read_first_chain(args.seq_fasta)
    muts = [m.strip() for m in args.mutate.split(",")] if args.mutate else None
    seq = _apply_mutations(seq, muts)
    if muts:
        print(f"applied mutations {muts}")

    if args.apo:
        # apo = homodimer, no ligand, no affinity (the matched two-state reference)
        lines = ["version: 1", "sequences:"]
        for ch in chains:
            lines += ["  - protein:", f"      id: {ch}", f"      sequence: {seq}"]
        out = os.path.join(args.out_dir, f"{args.prefix}_apo.yaml")
        with open(out, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"apo: -> {out}")
        return

    assert args.panel_csv, "--panel_csv required unless --apo"
    for row in csv.DictReader(open(args.panel_csv)):
        name = row["name"].strip()
        smiles = row["smiles"].strip()
        out = os.path.join(args.out_dir, f"{args.prefix}_{name}.yaml")
        build_holo_yaml(out, seq, smiles, chains=chains)
        print(f"{name}: -> {out}")


if __name__ == "__main__":
    main()
