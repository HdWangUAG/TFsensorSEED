"""Summarise the steroid structural dataset + plot multi-ligand proteins.

After sequence dedup, each (unique protein sequence, steroid) is one datapoint.
A protein sequence that binds *several different* steroids is the structural
basis for relative binding-preference: we can see which steroids the same pocket
accommodates and (with affinity) how it ranks them. This script quantifies that
and renders two figures:

  1. histogram — # distinct steroids bound per unique protein sequence
  2. heatmap   — top multi-ligand proteins × steroid codes (which pocket binds what)

Run:
    PYTHONPATH=. ~/LC-Seed/envs/app/.venv/bin/python -m tfsensor.ml.data.dataset_stats \
        --manifest data/ml/dataset_manifest.csv --out_dir results/ml_phase1/figures
"""
from __future__ import annotations

import argparse
import csv
import os
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load_structural(manifest):
    rows = [r for r in csv.DictReader(open(manifest)) if r.get("source") == "lcseed"]
    return rows


def per_protein(rows):
    """seq_hash -> {ligands:set, cath, pdbs:set}."""
    d = defaultdict(lambda: {"ligands": set(), "cath": "", "pdbs": set()})
    for r in rows:
        key = r.get("seq_hash") or f"pdb:{r['pdb']}"
        d[key]["ligands"].add(r["ligand_code"])
        d[key]["pdbs"].add(r["pdb"])
        if not d[key]["cath"] and r.get("receptor"):
            d[key]["cath"] = r["receptor"]
    return d


def summarise(rows):
    prot = per_protein(rows)
    nlig = Counter(len(v["ligands"]) for v in prot.values())
    multi = {k: v for k, v in prot.items() if len(v["ligands"]) >= 2}
    # structural co-binding pairs available (within-pocket ligand pairs)
    pairs = sum(len(v["ligands"]) * (len(v["ligands"]) - 1) // 2
                for v in prot.values())
    return {
        "n_datapoints": len(rows),
        "n_unique_proteins": len(prot),
        "n_multiligand_proteins": len(multi),
        "within_pocket_pairs": pairs,
        "dist_ligands_per_protein": dict(sorted(nlig.items())),
        "proteins": prot,
        "multi": multi,
    }


def plot_histogram(summary, out_png):
    dist = summary["dist_ligands_per_protein"]
    xs = sorted(dist)
    ys = [dist[x] for x in xs]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(xs, ys, color="#1b9e77", edgecolor="black", linewidth=0.4)
    ax.set_yscale("log")
    ax.set_xlabel("# distinct steroids bound by one protein sequence")
    ax.set_ylabel("# protein sequences (log)")
    ax.set_title(f"Steroid co-binding per protein  "
                 f"({summary['n_multiligand_proteins']} multi-ligand of "
                 f"{summary['n_unique_proteins']})")
    for x, y in zip(xs, ys):
        ax.text(x, y, str(y), ha="center", va="bottom", fontsize=7)
    fig.tight_layout()
    fig.savefig(out_png, dpi=200)
    plt.close(fig)


def plot_heatmap(summary, out_png, top_n=25, max_codes=30):
    multi = summary["multi"]
    top = sorted(multi.items(), key=lambda kv: -len(kv[1]["ligands"]))[:top_n]
    # columns = steroid codes most common among the top proteins
    code_counts = Counter()
    for _, v in top:
        code_counts.update(v["ligands"])
    codes = [c for c, _ in code_counts.most_common(max_codes)]
    mat = np.zeros((len(top), len(codes)))
    rlabels = []
    for i, (k, v) in enumerate(top):
        rep_pdb = sorted(v["pdbs"])[0]
        cath = v["cath"] or "?"
        rlabels.append(f"{rep_pdb} [{cath}] ({len(v['ligands'])})")
        for j, c in enumerate(codes):
            mat[i, j] = 1.0 if c in v["ligands"] else 0.0

    fig, ax = plt.subplots(figsize=(max(8, len(codes) * 0.35),
                                    max(5, len(top) * 0.32)))
    ax.imshow(mat, aspect="auto", cmap="Greens", vmin=0, vmax=1)
    ax.set_xticks(range(len(codes)))
    ax.set_xticklabels(codes, rotation=90, fontsize=7)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(rlabels, fontsize=7)
    ax.set_title(f"Top {len(top)} multi-steroid proteins × steroid codes "
                 f"(rep. PDB [CATH] (#ligands))")
    fig.tight_layout()
    fig.savefig(out_png, dpi=200)
    plt.close(fig)


def _main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default="data/ml/dataset_manifest.csv")
    ap.add_argument("--out_dir", default="results/ml_phase1/figures")
    args = ap.parse_args()

    rows = load_structural(args.manifest)
    s = summarise(rows)
    os.makedirs(args.out_dir, exist_ok=True)
    h = os.path.join(args.out_dir, "ligands_per_protein.png")
    m = os.path.join(args.out_dir, "multiligand_proteins_heatmap.png")
    plot_histogram(s, h)
    plot_heatmap(s, m)

    print(f"structural datapoints: {s['n_datapoints']}")
    print(f"unique protein sequences: {s['n_unique_proteins']}")
    print(f"multi-ligand proteins (>=2 distinct steroids): "
          f"{s['n_multiligand_proteins']}")
    print(f"within-pocket structural ligand pairs: {s['within_pocket_pairs']}")
    print(f"distribution (#steroids: #proteins): {s['dist_ligands_per_protein']}")
    top = sorted(s["multi"].items(), key=lambda kv: -len(kv[1]["ligands"]))[:8]
    print("top multi-steroid proteins:")
    for k, v in top:
        print(f"  {sorted(v['pdbs'])[0]} [{v['cath'] or '?'}] "
              f"{len(v['ligands'])} steroids: {sorted(v['ligands'])[:10]}")
    print(f"figures -> {h}\n           {m}")


if __name__ == "__main__":
    _main()
