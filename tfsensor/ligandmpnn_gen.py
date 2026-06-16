"""Stage-3 Tier-0: motif-anchored LigandMPNN generation.

Hypothesis-driven (NOT blind) pocket design on the estradiol-holo scaffold:
  * HARDCODE the "Estrogen Anchor": position 123 (WT Arg) is forced to GLU/ASP via
    omit_AA_per_residue (omit all AAs except D,E) — the carboxylate clamp for
    estradiol's 3-OH phenol (LAB_MANUAL Design Rule 1).
  * REDESIGN the rest of the ligand-pocket (1st/2nd shell) so MPNN repacks around the
    anchor for stability, ligand-aware (estradiol atoms in context).
  * Enforce HOMODIMER symmetry (tie chain-A position i to chain-B position i) so the
    pocket stays symmetric.

Drives LigandMPNN's run.py in its own venv; all tool/env paths come from
tfsensor.config (env vars / .env / defaults) and are overridable via --lmpnn_*.
Output: a deduped sequence library + per-design mutation list (vs WT) for the
Tier-1 ΔΔG screen.

    python -m tfsensor.ligandmpnn_gen --scaffold <estradiol_holo.pdb> \
        --out_dir results/stage3_design/gen --n_seqs 1000
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess

from tfsensor import config

# Resolved from env / .env / defaults (see tfsensor/config.py); overridable per-run
# via the run() kwargs and the --lmpnn_* CLI flags.
LMPNN = config.LMPNN_RUN
LMPNN_PY = config.LMPNN_PY
LMPNN_CKPT = config.LMPNN_CKPT
LMPNN_REPO = config.LMPNN_REPO

# ligand-pocket positions (model numbering) designed on BOTH chains; 123 = anchor
POCKET = [61, 85, 88, 96, 100, 106, 119, 122, 123, 143, 144, 146, 147, 151]
ANCHOR_POS = 123
ANCHOR_KEEP = "DE"                     # force Glu/Asp at the anchor
ALL_AA = "ACDEFGHIKLMNPQRSTVWY"


def _wt_seq(fasta="data/AcrR_dimer.fasta"):
    seq, started = [], False
    for line in open(fasta):
        if line.startswith(">"):
            if started:
                break
            started = True
            continue
        if started:
            seq.append(line.strip())
    return "".join(seq)


def _write_specs(out_dir, design_res, anchor, favor):
    """Build redesigned/symmetry + optional per-position omit (anchor) and bias (favor).

    design_res : list of model positions to redesign (applied to both chains).
    anchor     : (pos, keep_aa) -> force only keep_aa at that pos (omit the rest). Or None.
    favor      : (aa_string, weight) -> heavily favor those AAs at ALL design positions
                 via bias_AA_per_residue. Or None.
    Returns (redesigned, omit_json|None, bias_json|None, symmetry, symmetry_w).
    """
    os.makedirs(out_dir, exist_ok=True)
    redesigned = " ".join(f"{c}{p}" for c in ("A", "B") for p in design_res)
    omit_json = None
    if anchor:
        pos, keep = anchor
        omit_not = "".join(a for a in ALL_AA if a not in keep)
        omit = {f"A{pos}": omit_not, f"B{pos}": omit_not}
        omit_json = os.path.join(out_dir, "omit_AA_per_residue.json")
        json.dump(omit, open(omit_json, "w"), indent=2)
    bias_json = None
    if favor:
        aas, w = favor
        biasd = {f"{c}{p}": {a: w for a in aas} for c in ("A", "B") for p in design_res}
        bias_json = os.path.join(out_dir, "bias_AA_per_residue.json")
        json.dump(biasd, open(bias_json, "w"), indent=2)
    symmetry = "|".join(f"A{p},B{p}" for p in design_res)
    symmetry_w = "|".join("0.5,0.5" for _ in design_res)
    return redesigned, omit_json, bias_json, symmetry, symmetry_w


def run(scaffold, out_dir, n_seqs, temperatures, seed=1,
        design_res=None, anchor=(ANCHOR_POS, ANCHOR_KEEP), favor=None,
        lmpnn_py=None, lmpnn_run=None, lmpnn_ckpt=None, lmpnn_repo=None):
    # tool locations: explicit arg > config (env/.env) > historical default
    lmpnn_py = lmpnn_py or LMPNN_PY
    lmpnn_run = lmpnn_run or LMPNN
    lmpnn_ckpt = lmpnn_ckpt or LMPNN_CKPT
    lmpnn_repo = lmpnn_repo or LMPNN_REPO
    # LigandMPNN runs with cwd=lmpnn_repo, so ALL paths must be absolute.
    scaffold = os.path.abspath(scaffold)
    out_dir = os.path.abspath(out_dir)
    design_res = design_res or POCKET
    redesigned, omit_json, bias_json, symmetry, symmetry_w = _write_specs(
        out_dir, design_res, anchor, favor)
    batch_size = 10
    per_temp = max(1, n_seqs // (len(temperatures) * batch_size))
    print(f"[gen] redesign {len(design_res)} positions/2 chains; "
          f"anchor={anchor} favor={favor}; "
          f"{len(temperatures)} temps x {per_temp} batches x {batch_size} = "
          f"~{len(temperatures) * per_temp * batch_size} seqs", flush=True)
    for t in temperatures:
        od = os.path.join(out_dir, f"T{t}")
        cmd = [lmpnn_py, lmpnn_run,
               "--model_type", "ligand_mpnn",
               "--checkpoint_ligand_mpnn", lmpnn_ckpt,
               "--pdb_path", scaffold,
               "--out_folder", od,
               "--redesigned_residues", redesigned,
               "--symmetry_residues", symmetry,
               "--symmetry_weights", symmetry_w,
               "--ligand_mpnn_use_atom_context", "1",
               "--temperature", str(t),
               "--number_of_batches", str(per_temp),
               "--batch_size", str(batch_size),
               "--seed", str(seed),
               "--file_ending", f"_T{t}"]
        if omit_json:
            cmd += ["--omit_AA_per_residue", omit_json]
        if bias_json:
            cmd += ["--bias_AA_per_residue", bias_json]
        print(f"[gen] LigandMPNN T={t} -> {od}", flush=True)
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=lmpnn_repo)
        if r.returncode != 0:
            print(f"[gen][warn] T={t} failed:\n{r.stderr[-1500:]}")
    return _collect(out_dir)


def _iter_fasta(path):
    """Yield (header_text, sequence) per record; accumulates wrapped sequence lines."""
    header, chunks = None, []
    with open(path) as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith(">"):
                if header is not None:
                    yield header, "".join(chunks)
                header, chunks = line[1:], []
            elif line.strip():
                chunks.append(line.strip())
    if header is not None:
        yield header, "".join(chunks)


def _parse_header(header):
    """LigandMPNN header -> dict. Design records carry `id=`, `seq_rec=`, etc.;
    the first (native/input) record has none of these, only `num_res=`."""
    meta = {}
    parts = [p.strip() for p in header.split(",")]
    if parts and "=" not in parts[0]:
        meta["name"] = parts[0]
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            meta[k.strip()] = v.strip()
    return meta


def _select_chain(seq, expected_len, want_chain="A", chain_order=("A", "B")):
    """Extract one chain's sequence from a multi-chain MPNN record.

    Robust to the chain separator (':' or '/') and to block reordering: it honours
    the positional chain map only when that block's length matches the expected
    chain length, otherwise falls back to any block of the right length. Returns
    None if no block plausibly matches (record is then skipped, not mis-parsed)."""
    blocks = [b.strip() for b in re.split(r"[:/]", seq.strip()) if b.strip()]
    if not blocks:
        return None
    if want_chain in chain_order:
        i = chain_order.index(want_chain)
        if i < len(blocks) and len(blocks[i]) == expected_len:
            return blocks[i]
    for b in blocks:                       # fallback: first block of the expected length
        if len(b) == expected_len:
            return b
    return None


def _collect(out_dir, want_chain="A", chain_order=("A", "B")):
    """Parse all output FASTAs -> deduped library of (id, chain seq, mutations vs WT)."""
    import glob
    wt = _wt_seq()
    L = len(wt)
    seen, lib = set(), []
    n_native = n_badchain = 0
    fas = glob.glob(os.path.join(out_dir, "T*", "seqs", "*.fa")) + \
        glob.glob(os.path.join(out_dir, "T*", "seqs", "*.fasta"))
    for fa in fas:
        for header, seq in _iter_fasta(fa):
            meta = _parse_header(header)
            if "id" not in meta:           # native/input record (no design id) -> skip
                n_native += 1
                continue
            chain = _select_chain(seq, L, want_chain, chain_order)
            if chain is None:              # couldn't confidently locate the chain
                n_badchain += 1
                continue
            if chain == wt or chain in seen:
                continue
            seen.add(chain)
            muts = [f"{wt[i]}{i+1}{chain[i]}" for i in range(L) if chain[i] != wt[i]]
            lib.append({"id": f"des{len(lib):04d}", "seq": chain,
                        "mutations": muts, "n_mut": len(muts),
                        "source": header, "src_file": os.path.basename(fa),
                        "src_id": meta.get("id"), "seq_rec": meta.get("seq_rec")})
    if n_badchain:
        print(f"[gen][warn] skipped {n_badchain} record(s) with no chain matching "
              f"expected length {L}", flush=True)
    out_json = os.path.join(out_dir, "..", "library.json")
    out_json = os.path.normpath(out_json)
    json.dump(lib, open(out_json, "w"), indent=2)
    print(f"[gen] collected {len(lib)} unique designs -> {out_json}")
    if lib:
        anchored = sum(1 for d in lib if any(m[1:-1] == str(ANCHOR_POS) and m[-1] in ANCHOR_KEEP
                                             for m in d["mutations"]))
        print(f"[gen] designs with anchor {ANCHOR_POS}->{ANCHOR_KEEP}: {anchored}/{len(lib)}")
    return lib


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scaffold", required=True, help="estradiol-holo PDB (chains A,B + ligand)")
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--n_seqs", type=int, default=1000)
    ap.add_argument("--temperatures", default="0.1,0.2,0.3")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--collect_only", action="store_true")
    ap.add_argument("--design_residues", default=None,
                    help="space/comma model positions to redesign (default = full pocket)")
    ap.add_argument("--anchor", default="123:DE",
                    help="force-keep AAs at a position, e.g. '123:DE'; 'none' to disable "
                         "(use 'none' for the testosterone D-ring campaign that keeps WT Arg123)")
    ap.add_argument("--favor", default=None,
                    help="heavily favor AAs at all design positions, e.g. 'WFI:2.5' "
                         "(D-ring steric-clash bump)")
    # tool locations: default from config (env/.env), overridable here
    ap.add_argument("--lmpnn_py", default=None, help="python interpreter for LigandMPNN env")
    ap.add_argument("--lmpnn_run", default=None, help="path to LigandMPNN run.py")
    ap.add_argument("--lmpnn_ckpt", default=None, help="LigandMPNN checkpoint .pt")
    ap.add_argument("--lmpnn_repo", default=None, help="LigandMPNN repo dir (subprocess cwd)")
    args = ap.parse_args()
    temps = [t.strip() for t in args.temperatures.split(",") if t.strip()]
    if args.collect_only:
        _collect(args.out_dir)
        return
    design_res = None
    if args.design_residues:
        design_res = [int(x) for x in args.design_residues.replace(",", " ").split()]
    anchor = None
    if args.anchor and args.anchor.lower() != "none":
        pos, keep = args.anchor.split(":")
        anchor = (int(pos), keep)
    favor = None
    if args.favor:
        aas, w = args.favor.split(":")
        favor = (list(aas), float(w))
    run(args.scaffold, args.out_dir, args.n_seqs, temps, args.seed,
        design_res=design_res, anchor=anchor, favor=favor,
        lmpnn_py=args.lmpnn_py, lmpnn_run=args.lmpnn_run,
        lmpnn_ckpt=args.lmpnn_ckpt, lmpnn_repo=args.lmpnn_repo)


if __name__ == "__main__":
    main()
