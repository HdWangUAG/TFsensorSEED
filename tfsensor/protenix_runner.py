"""Build Protenix inputs and parse confidence for the orthogonal Track-B signal.

Protenix v2 has NO trained affinity head (only a ConfidenceHead). So for steroid
specificity it contributes an *orthogonal* signal: an independent holo pose plus
interface-confidence metrics (ligand-ipTM / pocket-pLDDT / interface-PAE). A
physics interface dG on the Protenix pose is computed separately (physics_score).

This module (a) writes the Protenix JSON inputs for the AcrR homodimer + steroid
panel, and (b) parses Protenix output confidence summaries into a per-steroid
record. The exact output layout is validated against a real run before use.

Protenix CLI (conda env ``protenix2``):
    protenix pred -i <inputs_dir_or_json> -o <out_dir> -s 1,42,2024 \
        -e 5 --use_msa True -n protenix_base_default_v1.0.0

CLI (input building):
    python -m tfsensor.protenix_runner build --seq_fasta data/AcrR_dimer.fasta \
        --panel_csv data/steroid_panel.csv --out_dir results/stage1_wt_validation/protenix/inputs \
        --prefix wt
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os


def _read_first_chain(fasta_path):
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
    """mutations: list of 'pos:AA' (1-based predictor numbering). Returns mutated seq.

    Applied to the single chain that is then replicated ``count`` times, so the
    homodimer stays symmetric (both chains mutated identically).
    """
    if not mutations:
        return seq
    s = list(seq)
    for m in mutations:
        pos, aa = m.split(":")
        pos = int(pos)
        assert 1 <= pos <= len(s), f"mutate pos {pos} out of range 1..{len(s)}"
        s[pos - 1] = aa
    return "".join(s)


def build_protenix_json(out_path, name, sequence, smiles, *, n_protein=2, n_ligand=2):
    """Write a Protenix inference JSON: homodimer (count=n_protein) + n_ligand copies.

    AcrR is a homodimer with one effector pocket per monomer, so the physiological holo
    state has n_ligand = n_protein (default 2 — both pockets occupied).
    """
    job = [{
        "name": name,
        "sequences": [
            {"proteinChain": {"sequence": sequence, "count": n_protein}},
            {"ligand": {"ligand": smiles, "count": n_ligand}},
        ],
    }]
    json.dump(job, open(out_path, "w"), indent=2)
    return out_path


def cmd_build(args):
    os.makedirs(args.out_dir, exist_ok=True)
    seq = _read_first_chain(args.seq_fasta)
    muts = [m.strip() for m in args.mutate.split(",")] if args.mutate else None
    seq = _apply_mutations(seq, muts)
    if muts:
        print(f"applied mutations {muts}")
    for row in csv.DictReader(open(args.panel_csv)):
        name = f"{args.prefix}_{row['name'].strip()}"
        out = os.path.join(args.out_dir, f"{name}.json")
        build_protenix_json(out, name, seq, row["smiles"].strip(),
                            n_protein=args.n_protein, n_ligand=args.n_ligand)
        print(f"{row['name']}: -> {out}  (protein x{args.n_protein}, ligand x{args.n_ligand})")


# ---- output parsing (validated against a real Protenix v2 run) -------------
# Output layout: <out>/<job>/seed_<S>/predictions/<job>_summary_confidence_sample_<i>.json
# The ligand is the LAST chain, so its interface confidence is chain_iptm[-1] /
# chain_plddt[-1]; chain_pair_pae_min[-1][:-1] are the ligand..protein interface PAEs.


def _ligand_metrics(d):
    """Extract ligand-interface confidence from one summary_confidence dict."""
    ci = d.get("chain_iptm") or []
    cp = d.get("chain_plddt") or []
    pae = d.get("chain_pair_pae_min") or []
    lig_iptm = ci[-1] if ci else None
    lig_plddt = cp[-1] if cp else None
    lig_pae = None
    if pae and len(pae[-1]) > 1:
        lig_pae = min(pae[-1][:-1])      # best ligand..protein interface PAE
    return lig_iptm, lig_plddt, lig_pae


def analyze_job(out_dir, job_name, seed=None):
    """Aggregate samples for one Protenix job (optionally one seed) into a record.

    Picks the best sample by ranking_score; also reports the mean ligand-ipTM
    across all samples (the seed/sample-robust orthogonal signal). Pass ``seed``
    to restrict to a single ``seed_<seed>`` directory.
    """
    seed_glob = f"seed_{seed}" if seed is not None else "seed_*"
    files = sorted(glob.glob(os.path.join(
        out_dir, job_name, seed_glob, "predictions",
        f"{job_name}_summary_confidence_sample_*.json")))
    if not files:
        files = sorted(glob.glob(os.path.join(
            out_dir, "**", f"*{job_name}*summary_confidence*.json"), recursive=True))
    best, samples = None, []
    for f in files:
        d = json.load(open(f))
        lig_iptm, lig_plddt, lig_pae = _ligand_metrics(d)
        rec = {
            "summary_json": f,
            "ranking_score": d.get("ranking_score"),
            "iptm": d.get("iptm"), "ptm": d.get("ptm"), "plddt": d.get("plddt"),
            "ligand_iptm": lig_iptm, "ligand_plddt": lig_plddt,
            "ligand_pae_min": lig_pae, "has_clash": d.get("has_clash"),
            "cif": f.replace("_summary_confidence_", "_").replace(".json", ".cif"),
        }
        samples.append(rec)
        rs = rec["ranking_score"] or 0
        if best is None or rs > (best["ranking_score"] or 0):
            best = rec
    if not samples:
        return None
    def _mean(key):
        vals = [s[key] for s in samples if s[key] is not None]
        return round(sum(vals) / len(vals), 4) if vals else None
    return {"job": job_name, "n_samples": len(samples), "best": best,
            "mean_ligand_iptm": _mean("ligand_iptm"),
            "mean_ligand_plddt": _mean("ligand_plddt"),
            "mean_ligand_pae_min": _mean("ligand_pae_min")}


def cmd_parse(args):
    rec = analyze_job(args.out_dir, args.job_name)
    print(json.dumps(rec, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="write Protenix JSON inputs")
    b.add_argument("--seq_fasta", required=True)
    b.add_argument("--panel_csv", required=True)
    b.add_argument("--out_dir", required=True)
    b.add_argument("--prefix", default="wt")
    b.add_argument("--n_protein", type=int, default=2)
    b.add_argument("--n_ligand", type=int, default=2,
                   help="ligand copies (homodimer = 2, one per pocket)")
    b.add_argument("--mutate", default=None,
                   help="comma-sep pos:AA (1-based predictor numbering), applied to the chain")
    b.set_defaults(func=cmd_build)

    p = sub.add_parser("parse", help="parse Protenix confidence output")
    p.add_argument("--out_dir", required=True, help="protenix -o output dir")
    p.add_argument("--job_name", required=True)
    p.set_defaults(func=cmd_parse)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
