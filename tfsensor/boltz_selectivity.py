"""Read AcrR steroid selectivity from Boltz-2 holo predictions.

Adapted from AcylSEED ``fatb/boltz_selectivity.py``. Differences for AcrR:
  * The ligand is a RIGID steroid -> use ALL ligand heavy atoms (no acyl-tail
    identification).
  * The pocket is the AcrR steroid site (resnums from the 4.5 A STR contact scan,
    chain-agnostic so it matches whichever symmetric site the ligand picks).
  * Panel is keyed by steroid NAME (estradiol/testosterone/...), not chain length.

Primary metric: ``affinity_probability_binary`` (binder likelihood; HIGHER =
preferred). ``affinity_pred_value`` is reported but is size-biased — do not rank on it.

CLI:
    python -m tfsensor.boltz_selectivity \
        --series label=WT:results/stage1_wt_validation/boltz/seed1 \
        --pocket data/pocket_residues.json --panel data/steroid_panel.csv \
        --out_dir results/stage1_wt_validation/boltz
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os

import numpy as np

CONTACT = 4.5          # ligand-atom .. pocket-residue-atom contact cutoff (A)
MIN_CONTACTS = 4       # >= this many pocket residues in contact => seated


def load_pocket(pocket_json):
    """Chain-agnostic set of pocket resSeqs from prep_receptor's scan output."""
    hits = json.load(open(pocket_json))
    return {h["resSeq"] for h in hits}


def load_panel_names(panel_csv):
    return [r["name"].strip() for r in csv.DictReader(open(panel_csv))]


def _load_complex(pdb_path):
    """Return (prot[(chain,resSeq)] -> (M,3) heavy-atom coords, ligand (L,3))."""
    prot, lig = {}, []
    for l in open(pdb_path):
        rec = l[:6].strip()
        if rec == "ATOM":
            el = (l[76:78].strip() or l[12:16].strip()[0]).upper()
            if el == "H":
                continue
            key = (l[21], int(l[22:26]))
            prot.setdefault(key, []).append(
                [float(l[30:38]), float(l[38:46]), float(l[46:54])])
        elif rec == "HETATM":
            resname = l[17:20].strip()
            if resname in ("HOH", "WAT"):
                continue
            el = (l[76:78].strip() or l[12:16].strip()[0]).upper()
            if el == "H":
                continue
            lig.append([float(l[30:38]), float(l[38:46]), float(l[46:54])])
    prot = {k: np.array(v) for k, v in prot.items()}
    lig = np.array(lig) if lig else None
    return prot, lig


def _pocket_check(prot, lig, pocket):
    """(contacts list 'A61', seated bool) for one model."""
    if lig is None:
        return [], False
    contacts = []
    for (ch, rn), atoms in prot.items():
        if rn in pocket:
            dmin = np.linalg.norm(lig[:, None] - atoms[None], axis=2).min()
            if dmin < CONTACT:
                contacts.append(f"{ch}{rn}")
    seated = len(contacts) >= MIN_CONTACTS
    return sorted(contacts), seated


def analyze_prediction(pred_dir, pocket):
    """One Boltz prediction dir -> selectivity record (best seated model)."""
    name = os.path.basename(pred_dir.rstrip("/"))
    aff = json.load(open(os.path.join(pred_dir, f"affinity_{name}.json")))
    models = sorted(glob.glob(os.path.join(pred_dir, f"{name}_model_*.pdb")))
    seated_best, any0, n_seated = None, None, 0
    for mp in models:
        mi = int(mp.rsplit("_model_", 1)[1].split(".")[0])
        conf = json.load(open(os.path.join(
            pred_dir, f"confidence_{name}_model_{mi}.json")))["confidence_score"]
        prot, lig = _load_complex(mp)
        contacts, seated = _pocket_check(prot, lig, pocket)
        rec = {"model": mi, "conf": conf, "contacts": contacts, "seated": seated}
        n_seated += int(seated)
        if mi == 0:
            any0 = rec
        if seated and (seated_best is None or conf > seated_best["conf"]):
            seated_best = rec
    chosen = seated_best or any0
    return {
        "name": name,
        "affinity_probability_binary": aff.get("affinity_probability_binary"),
        "affinity_pred_value": aff.get("affinity_pred_value"),
        "conf_model0": any0["conf"] if any0 else None,
        "n_seated_models": n_seated,
        "n_models": len(models),
        "chosen_model": chosen["model"] if chosen else None,
        "chosen_seated": bool(seated_best),
        "chosen_contacts": chosen["contacts"] if chosen else [],
    }


def collect(parents, pocket):
    out = []
    for parent in parents:
        for pred in sorted(glob.glob(
                os.path.join(parent, "**", "predictions", "*"), recursive=True)):
            if os.path.isdir(pred):
                out.append(analyze_prediction(pred, pocket))
    return out


def _name_key(pred_name, panel_names):
    """Map a prediction dir name (e.g. 'wt_estradiol') to a steroid name."""
    for n in panel_names:
        if pred_name.endswith(n) or n in pred_name:
            return n
    return pred_name


def build_profile(records, panel_names):
    """records -> ({name: binder_prob}, {name: aff_pred}, preferred name)."""
    bp, av = {}, {}
    for r in records:
        key = _name_key(r["name"], panel_names)
        if r["affinity_probability_binary"] is not None:
            bp[key] = r["affinity_probability_binary"]
        if r["affinity_pred_value"] is not None:
            av[key] = r["affinity_pred_value"]
    preferred = max(bp, key=bp.get) if bp else None
    return bp, av, preferred


def plot_profiles(series_bp, series_av, panel_names, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    order = panel_names
    x = np.arange(len(order))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    for label, prof in series_bp.items():
        ys = [prof.get(n, np.nan) for n in order]
        axes[0].plot(x, ys, "o-", label=label)
        if prof:
            best = max(prof, key=prof.get)
            axes[0].scatter([order.index(best)], [prof[best]], s=170,
                            facecolors="none", edgecolors="red", linewidths=1.8, zorder=5)
    axes[0].set_ylabel("affinity_probability_binary\n(higher = preferred)  [PRIMARY]")
    axes[0].set_title("Boltz-2 binder-likelihood")
    for label, prof in series_av.items():
        axes[1].plot(x, [prof.get(n, np.nan) for n in order], "s--", label=label)
    axes[1].set_ylabel("affinity_pred_value (size-biased)")
    axes[1].set_title("Regressed affinity (do not rank on this)")
    axes[1].invert_yaxis()
    for ax in axes:
        ax.set_xticks(x); ax.set_xticklabels(order, rotation=20)
        ax.legend()
    fig.suptitle("AcrR steroid selectivity — Boltz-2 holo")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    return out_png


def _parse_labeled(specs):
    groups = {}
    for s in specs or []:
        label, _, path = s.partition(":")
        if label.startswith("label="):
            label = label[len("label="):]
        groups.setdefault(label, []).append(path)
    return groups


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--series", nargs="+", required=True,
                    help="label=NAME:PARENT_DIR (repeatable; same label merges)")
    ap.add_argument("--pocket", required=True, help="pocket_residues.json")
    ap.add_argument("--panel", required=True, help="steroid_panel.csv")
    ap.add_argument("--out_dir", required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    pocket = load_pocket(args.pocket)
    panel_names = load_panel_names(args.panel)
    groups = _parse_labeled(args.series)

    series_bp, series_av, all_records = {}, {}, {}
    for label, parents in groups.items():
        recs = collect(parents, pocket)
        all_records[label] = recs
        bp, av, preferred = build_profile(recs, panel_names)
        series_bp[label], series_av[label] = bp, av
        print(f"\n=== {label} ===  preferred (binder-prob) = {preferred}")
        print(f"{'steroid':>13} {'bind_prob':>9} {'aff_pred':>9} {'conf0':>6} "
              f"{'seated':>6} {'nseat':>6} {'model':>5} contacts")
        for r in recs:
            key = _name_key(r["name"], panel_names)
            print(f"{key:>13} {r['affinity_probability_binary']:>9.3f} "
                  f"{r['affinity_pred_value']:>9.3f} {r['conf_model0']:>6.3f} "
                  f"{str(r['chosen_seated']):>6} "
                  f"{r['n_seated_models']:>3}/{r['n_models']:<2} "
                  f"m{str(r['chosen_model']):<4} {r['chosen_contacts']}")

    json.dump({"binder_prob": series_bp, "affinity_pred": series_av,
               "records": all_records},
              open(os.path.join(args.out_dir, "boltz_selectivity.json"), "w"), indent=2)
    print(f"wrote {os.path.join(args.out_dir, 'boltz_selectivity.json')}")
    try:
        png = plot_profiles(series_bp, series_av, panel_names,
                            os.path.join(args.out_dir, "boltz_selectivity_profile.png"))
        print(f"wrote {png}")
    except ModuleNotFoundError as e:
        print(f"(plot skipped: {e}; run in an env with matplotlib for the figure)")


if __name__ == "__main__":
    main()
