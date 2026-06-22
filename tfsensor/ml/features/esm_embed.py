"""ESM-2 pocket/mutation-site embeddings for AcrR mutants (the P1 ablation feature).

Threads a mutation list onto the WT AcrR chain, runs ESM-2, and mean-pools the
per-residue representations over the MUTATED positions (the local context of the
change; WT pools over the pocket). This gives ESM's contextual view of each
substitution — the "position context" the physchem deltas lack.

Needs fair-esm + torch (e.g. ~/.conda/envs/pyrosetta). Precompute caches a
{model_mut: vector} npz so the (sklearn) benchmark can read it from any env.

    ~/.conda/envs/pyrosetta/bin/python -m tfsensor.ml.features.esm_embed
"""
from __future__ import annotations

import os
import numpy as np

from tfsensor import config
from tfsensor.ml.bo import seed, physchem

FASTA = os.path.join(config.REPO_ROOT, "data/AcrR_dimer.fasta")
CACHE = os.path.join(config.REPO_ROOT, "data/ml/esm_cache/scan_esm.npz")
MODEL = "esm2_t12_35M_UR50D"   # small/fast; bump to t33_650M if it shows signal


def wt_seq(fasta=FASTA):
    seq = []
    for line in open(fasta):
        if line.startswith(">"):
            if seq:
                break
            continue
        seq.append(line.strip())
    return "".join(seq)


def _thread(seq, mutations):
    """Apply mutations; return (seq, ok). ok=False if any stated WT mismatches
    the sequence (numbering misalignment) — caller skips those variants."""
    s = list(seq)
    ok = True
    for wt, pos, aa in mutations:
        if not (1 <= pos <= len(s)) or s[pos - 1] != wt:
            ok = False
            continue
        s[pos - 1] = aa
    return "".join(s), ok


def precompute(out=CACHE, model_name=MODEL):
    import torch
    import esm
    wt = wt_seq()
    pocket = sorted(physchem.ligand_distances().items(), key=lambda kv: kv[1])
    pocket_idx = [p - 1 for p, _ in pocket[:14]]            # 14 nearest residues
    variants, muts, _ = seed.objective_table("testosterone")  # all variants incl WT

    model, alphabet = getattr(esm.pretrained, model_name)()
    model.eval()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(dev)
    bc = alphabet.get_batch_converter()
    layer = model.num_layers

    out_keys, out_vecs, skipped = [], [], 0
    for v, mut in zip(variants, muts):
        s, ok = _thread(wt, mut)
        if not ok:
            skipped += 1
            continue
        _, _, toks = bc([(v, s)])
        with torch.no_grad():
            rep = model(toks.to(dev), repr_layers=[layer])["representations"][layer][0]
        rep = rep[1:len(s) + 1]                             # drop BOS/EOS
        idx = [p - 1 for _, p, _ in mut] if mut else pocket_idx
        vec = rep[idx].mean(0).cpu().numpy()
        out_keys.append(v); out_vecs.append(vec)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    np.savez(out, keys=np.array(out_keys), vecs=np.vstack(out_vecs))
    print(f"cached {len(out_keys)} ESM-{model_name} embeddings "
          f"({out_vecs[0].shape[0]}-dim), skipped {skipped} (numbering mismatch) -> {out}")


def load_cache(path=CACHE):
    d = np.load(path, allow_pickle=True)
    return {str(k): v for k, v in zip(d["keys"], d["vecs"])}


if __name__ == "__main__":
    precompute()
