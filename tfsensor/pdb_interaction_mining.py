"""First-principles steroid recognition from observed PDB contacts.

Mines the PDBe graph-api atom-level interaction data for each panel steroid
(STR=progesterone, TES=testosterone, EST=estradiol, HCY=cortisol) across EVERY
PDB structure that binds it, and aggregates a data-driven recognition fingerprint:
which ligand atoms (esp. the oxygens / functional groups) make polar (H-bond/ionic)
vs hydrophobic contacts, and which protein residue types provide them.

This grounds the design rationale in experiment: the steroid oxygens that are
consistently H-bonded are the specificity anchors, and the residue types that
serve them tell us what to install in the AcrR pocket (e.g. why an Arg, L147R,
recruits the polar cortisol).

Endpoints (public, no auth):
  entries:      api/pdb/compound/in_pdb/<CODE>
  instances:    graph-api/pdb/bound_molecules/<pdb>
  interactions: graph-api/pdb/bound_ligand_interactions/<pdb>/<chain>/<resnum>

    python -m tfsensor.pdb_interaction_mining --out_dir results/stage1e_pdbmine
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.request
from collections import Counter, defaultdict

API = "https://www.ebi.ac.uk/pdbe/api"
GRAPH = "https://www.ebi.ac.uk/pdbe/graph-api"
CODES = {"STR": "progesterone", "TES": "testosterone",
         "EST": "estradiol", "HCY": "cortisol"}

# polar / H-bond-like interaction vocabulary (PDBe/arpeggio terms) vs hydrophobic
POLAR = {"hbond", "hydrogen bond", "weak_hbond", "weak hydrogen bond", "polar",
         "ionic", "salt bridge", "metal", "carbonyl", "amide", "xbond", "halogen bond"}
HYDROPHOBIC = {"hydrophobic", "vdw", "van der waals"}
AROMATIC = {"aromatic", "pi-stacking", "pi-pi", "cation-pi", "carbonpi",
            "donorpi", "pi-cation", "aromatic contact"}


def _cache_get(url, cache_dir, pause=0.05):
    os.makedirs(cache_dir, exist_ok=True)
    key = hashlib.md5(url.encode()).hexdigest() + ".json"
    path = os.path.join(cache_dir, key)
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except Exception:
            pass
    try:
        with urllib.request.urlopen(url, timeout=40) as r:
            data = json.load(r)
    except Exception as e:
        data = {"_error": str(e)}
    json.dump(data, open(path, "w"))
    time.sleep(pause)
    return data


def entries(code, cache_dir):
    d = _cache_get(f"{API}/pdb/compound/in_pdb/{code}", cache_dir)
    return [e["pdb_id"] for e in d.get(code, [])]


def instances(pdb, code, cache_dir):
    d = _cache_get(f"{GRAPH}/pdb/bound_molecules/{pdb}", cache_dir)
    out = []
    for bm in d.get(pdb, []):
        for lig in bm.get("composition", {}).get("ligands", []):
            if lig.get("chem_comp_id") == code:
                out.append((lig["chain_id"], lig["author_residue_number"]))
    return out


def interactions(pdb, chain, resnum, cache_dir):
    url = f"{GRAPH}/pdb/bound_ligand_interactions/{pdb}/{chain}/{resnum}"
    d = _cache_get(url, cache_dir)
    recs = []
    for blk in d.get(pdb, []):
        recs += blk.get("interactions", [])
    return recs


def _bucket(details):
    s = {x.lower() for x in details}
    if s & POLAR:
        return "polar"
    if s & AROMATIC:
        return "aromatic"
    if s & HYDROPHOBIC:
        return "hydrophobic"
    return "other"


def mine(code, cache_dir, max_entries=None):
    pdbs = entries(code, cache_dir)
    if max_entries:
        pdbs = pdbs[:max_entries]
    per_atom = defaultdict(lambda: Counter())          # atom -> {polar,hydrophobic,...}
    polar_partners = Counter()                          # restype making polar contact
    polar_partners_by_atom = defaultdict(Counter)       # ligand O atom -> restype
    type_vocab = Counter()
    n_inst = 0
    for pdb in pdbs:
        for (chain, resnum) in instances(pdb, code, cache_dir):
            n_inst += 1
            for it in interactions(pdb, chain, resnum, cache_dir):
                details = it.get("interaction_details", []) or []
                type_vocab.update(d.lower() for d in details)
                b = _bucket(details)
                end = it.get("end", {})
                restype = end.get("chem_comp_id", "?")
                for a in it.get("ligand_atoms", []) or ["?"]:
                    per_atom[a][b] += 1
                    if b == "polar":
                        polar_partners[restype] += 1
                        if a.startswith("O"):
                            polar_partners_by_atom[a][restype] += 1
    return {
        "code": code, "name": CODES.get(code, code),
        "n_entries": len(pdbs), "n_instances": n_inst,
        "per_atom": {a: dict(c) for a, c in per_atom.items()},
        "polar_partners": dict(polar_partners.most_common()),
        "polar_partners_by_oxygen": {a: dict(c.most_common())
                                     for a, c in polar_partners_by_atom.items()},
        "interaction_vocabulary": dict(type_vocab.most_common()),
    }


# chemical identity of each ligand oxygen (PDB component atom name -> group).
# Cortisol (HCY) uses generic O1..O5; mapped from its connectivity to the steroid
# positions (3-keto, 11beta-OH, 17alpha-OH, 20-keto, 21-OH).
OXY_LABELS = {
    "STR": {"O3": "3-keto (A-ring)", "O20": "20-keto (D-ring)"},
    "TES": {"O3": "3-keto (A-ring)", "O17": "17β-OH"},
    "EST": {"O3": "3-OH PHENOL (arom. A-ring)", "O17": "17β-OH"},
    # HCY oxygens verified from PDBe bond connectivity (O#->bonded C#):
    "HCY": {"O1": "3-keto (A-ring)", "O2": "11β-OH", "O3": "17α-OH",
            "O4": "20-keto", "O5": "21-OH"},
}


def _plots(summary, out_dir):
    """Publication figures from the mined fingerprint (needs matplotlib)."""
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.dpi": 150, "savefig.dpi": 300, "font.size": 10,
                         "font.family": "DejaVu Sans", "axes.spines.top": False,
                         "axes.spines.right": False, "pdf.fonttype": 42})
    order = ["TES", "STR", "HCY", "EST"]
    cset = {"TES": "#1b9e77", "STR": "#1b9e77", "HCY": "#d95f02", "EST": "#e7298a"}

    # ---- Fig A: per-oxygen polar fraction + #polar contacts per bound instance ----
    rows = []
    for code in order:
        s = summary[code]
        for a in sorted(s["per_atom"]):
            if not a.startswith("O"):
                continue
            c = s["per_atom"][a]; tot = sum(c.values()); pol = c.get("polar", 0)
            rows.append((code, a, OXY_LABELS.get(code, {}).get(a, a),
                         pol / tot if tot else 0, pol / max(s["n_instances"], 1)))
    fig, ax = plt.subplots(figsize=(10, 4.6))
    x = np.arange(len(rows))
    ax.bar(x, [r[4] for r in rows], color=[cset[r[0]] for r in rows])
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r[2]}" for r in rows], rotation=40, ha="right", fontsize=8.5)
    for i, r in enumerate(rows):
        ax.text(i, r[4] + 0.03, f"{r[3]:.0%}", ha="center", fontsize=8, color="#333")
    ax.set_ylabel("polar H-bond contacts per bound instance\n(label = % of that O's contacts that are polar)")
    ax.set_title("Steroid oxygen H-bond demand across the PDB (data-driven specificity anchors)",
                 fontsize=12, fontweight="bold")
    # group separators / steroid labels
    cum = 0
    for code in order:
        n = sum(1 for r in rows if r[0] == code)
        ax.text(cum + (n - 1) / 2, -0.42, f"{summary[code]['name']}\n(n={summary[code]['n_instances']})",
                ha="center", va="top", fontsize=9, fontweight="bold",
                color=cset[code], transform=ax.get_xaxis_transform())
        cum += n
        if cum < len(rows):
            ax.axvline(cum - 0.5, color="#ccc", lw=0.8)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(out_dir, f"fig_oxygen_hbond_demand.{ext}"),
                    bbox_inches="tight")
    plt.close(fig)

    # ---- Fig B: ligand-oxygen x partner residue-type heatmap (polar contacts) ----
    res_keep = ["GLU", "ASP", "ARG", "LYS", "HIS", "GLN", "ASN", "SER", "THR",
                "TYR", "TRP", "MET", "HOH"]
    rlabels, mat = [], []
    for code in order:
        s = summary[code]
        for a in sorted(s["polar_partners_by_oxygen"]):
            partners = s["polar_partners_by_oxygen"][a]
            tot = sum(partners.values()) or 1
            mat.append([partners.get(r, 0) / tot for r in res_keep])
            rlabels.append(f"{summary[code]['name'][:4]}·{OXY_LABELS.get(code,{}).get(a,a)}")
    mat = np.array(mat)
    fig, ax = plt.subplots(figsize=(0.62 * len(res_keep) + 2.5, 0.6 * len(rlabels) + 1.8))
    im = ax.imshow(mat, cmap="magma_r", vmin=0, vmax=max(0.6, mat.max()))
    ax.set_xticks(range(len(res_keep)))
    ax.set_xticklabels(res_keep, rotation=0, ha="center", fontsize=8.5, fontweight="bold")
    ax.set_yticks(range(len(rlabels))); ax.set_yticklabels(rlabels, fontsize=8.5)

    # --- side-chain structures under each x-axis residue label (RDKit) ---
    import io as _io
    from matplotlib.offsetbox import OffsetImage, AnnotationBbox
    import matplotlib.transforms as _mt
    from rdkit import Chem
    from rdkit.Chem.Draw import rdMolDraw2D as _d2d
    from PIL import Image
    SIDECHAIN = {  # CB-rooted side-chain fragment per residue (HOH = water)
        "GLU": "CCC(=O)O", "ASP": "CC(=O)O", "ARG": "CCCNC(=N)N", "LYS": "CCCCN",
        "HIS": "Cc1c[nH]cn1", "GLN": "CCC(N)=O", "ASN": "CC(N)=O", "SER": "CO",
        "THR": "C(C)O", "TYR": "Cc1ccc(O)cc1", "TRP": "Cc1c[nH]c2ccccc12",
        "MET": "CCSC", "HOH": "O"}

    def _sc_png(smiles, px=140):
        m = Chem.MolFromSmiles(smiles)
        if m is None:
            return None
        d = _d2d.MolDraw2DCairo(px, px)
        d.drawOptions().bondLineWidth = 2
        d.drawOptions().padding = 0.12
        _d2d.PrepareAndDrawMolecule(d, m)
        d.FinishDrawing()
        return np.array(Image.open(_io.BytesIO(d.GetDrawingText())))

    trans = _mt.blended_transform_factory(ax.transData, ax.transAxes)
    for j, res in enumerate(res_keep):
        png = _sc_png(SIDECHAIN.get(res, "")) if res in SIDECHAIN else None
        if png is None:
            continue
        ab = AnnotationBbox(OffsetImage(png, zoom=0.30), (j, -0.045), xycoords=trans,
                            box_alignment=(0.5, 1.0), frameon=False, pad=0.0)
        ab.set_clip_on(False)
        ax.add_artist(ab)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            if mat[i, j] >= 0.12:
                ax.text(j, i, f"{mat[i,j]:.0%}", ha="center", va="center",
                        fontsize=7, color="white" if mat[i, j] > 0.45 else "black")
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("fraction of that oxygen's polar contacts", fontsize=9)
    ax.set_title("Which residue type H-bonds each steroid oxygen (PDB-wide)\n"
                 "estradiol 3-OH → GLU/ARG clamp; cortisol polyol → SER/THR/ASN",
                 fontsize=11, fontweight="bold")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(out_dir, f"fig_partner_residue_heatmap.{ext}"),
                    bbox_inches="tight")
    plt.close(fig)
    print(f"[mine] wrote fig_oxygen_hbond_demand + fig_partner_residue_heatmap -> {out_dir}")


def run(out_dir, max_entries=None, plot=True):
    os.makedirs(out_dir, exist_ok=True)
    cache_dir = os.path.join(out_dir, "cache")
    summary = {}
    for code in CODES:
        print(f"[mine] {code} ({CODES[code]}) ...", flush=True)
        summary[code] = mine(code, cache_dir, max_entries)
        s = summary[code]
        print(f"   entries={s['n_entries']} instances={s['n_instances']} "
              f"vocab={list(s['interaction_vocabulary'])[:6]}")
    json.dump(summary, open(os.path.join(out_dir, "interaction_summary.json"), "w"),
              indent=2)
    if plot:
        try:
            _plots(summary, out_dir)
        except Exception as e:
            print(f"[mine] plotting skipped: {e}")

    # ----- console report: oxygen (polar-anchor) fingerprint -----
    print("\n==== OXYGEN / POLAR-ANCHOR FINGERPRINT (polar contacts per ligand oxygen) ====")
    for code in CODES:
        s = summary[code]
        oxys = {a: c for a, c in s["per_atom"].items() if a.startswith("O")}
        print(f"\n{code} ({s['name']}, {s['n_instances']} bound instances):")
        for a in sorted(oxys):
            c = oxys[a]
            tot = sum(c.values())
            polar = c.get("polar", 0)
            frac = polar / tot if tot else 0
            partners = s["polar_partners_by_oxygen"].get(a, {})
            top = ", ".join(f"{k}:{v}" for k, v in list(partners.items())[:4])
            print(f"   {a:4s} polar={polar:3d}/{tot:<3d} ({frac:0.0%})  "
                  f"hphob={c.get('hydrophobic',0):3d}  partners[{top}]")
        print(f"   top polar partners overall: "
              + ", ".join(f"{k}:{v}" for k, v in list(s['polar_partners'].items())[:6]))
    print(f"\n[mine] wrote {out_dir}/interaction_summary.json")
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out_dir", default="results/stage1e_pdbmine")
    ap.add_argument("--max_entries", type=int, default=None,
                    help="cap entries per compound (debug)")
    args = ap.parse_args()
    run(args.out_dir, args.max_entries)


if __name__ == "__main__":
    main()
