"""gnina baseline scorer (docking + CNN affinity).

gnina v1.3.x is a self-contained binary (config.GNINA_BIN). We dock each ligand
into the pocket defined by an autobox reference ligand and read the top pose's
``CNNaffinity`` (pKd-like; higher = stronger), ``CNNscore`` (pose quality), and
``minimizedAffinity`` (Vina kcal/mol; more negative = stronger).

CLI — score the AcrR steroid panel against the receptor:
    PYTHONPATH=. ~/LC-Seed/envs/app/.venv/bin/python -m tfsensor.ml.baselines.gnina \
        --panel
"""
from __future__ import annotations

import argparse
import os
import subprocess

from rdkit import Chem, RDLogger

from tfsensor import config
from tfsensor.ml.baselines.base import Scorer, extract_hetatm_ligand

RDLogger.DisableLog("rdApp.*")


class GninaScorer(Scorer):
    name = "gnina"

    def __init__(self, gnina_bin=None, num_modes=5, seed=0, cnn_scoring="rescore"):
        self.bin = gnina_bin or config.GNINA_BIN
        self.num_modes = num_modes
        self.seed = seed
        self.cnn_scoring = cnn_scoring

    def score(self, receptor_pdb, ligand_sdf, autobox_ligand=None, workdir=None):
        if autobox_ligand is None:
            raise ValueError("gnina needs an autobox_ligand (pocket reference)")
        workdir = workdir or "data/ml/cache/gnina"
        os.makedirs(workdir, exist_ok=True)
        tag = os.path.splitext(os.path.basename(ligand_sdf))[0]
        out_sdf = os.path.join(workdir, f"{tag}_docked.sdf")
        cmd = [
            self.bin, "-r", receptor_pdb, "-l", ligand_sdf,
            "--autobox_ligand", autobox_ligand, "-o", out_sdf,
            "--seed", str(self.seed), "--num_modes", str(self.num_modes),
            "--cnn_scoring", self.cnn_scoring,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return {"error": proc.stderr.strip().splitlines()[-1:] or "gnina failed",
                    "cmd": " ".join(cmd)}
        return self._parse_top_pose(out_sdf)

    @staticmethod
    def _parse_top_pose(out_sdf):
        supp = Chem.SDMolSupplier(out_sdf, sanitize=False)
        best = None
        for mol in supp:
            if mol is None:
                continue
            props = mol.GetPropsAsDict()
            cnn_aff = props.get("CNNaffinity")
            # gnina sorts by CNN by default; take the max CNNaffinity to be safe
            if cnn_aff is not None and (best is None or cnn_aff > best["affinity_pK"]):
                best = {
                    "affinity_pK": float(cnn_aff),
                    "pose_score": float(props.get("CNNscore", "nan")),
                    "dG_kcalmol": float(props.get("minimizedAffinity", "nan")),
                    "raw": {k: props[k] for k in props
                            if k.startswith("CNN") or "Affinity" in k},
                }
        return best or {"error": f"no parseable poses in {out_sdf}"}


# --- AcrR panel convenience runner -----------------------------------------
PANEL = ["testosterone", "cortisol", "progesterone", "estradiol"]
# Established WT ranking (LAB_MANUAL §1): test > cort > prog; estradiol non-responder.


def run_panel(receptor=None, holo=None, lig_resname="STR", ligand_dir="data/ligands"):
    receptor = receptor or os.path.join(config.REPO_ROOT, "data/AcrR_protein_only.pdb")
    holo = holo or os.path.join(config.REPO_ROOT, "data/AcrR_STR_001.pdb")
    autobox = extract_hetatm_ligand(holo, lig_resname,
                                    "data/ml/cache/gnina/autobox_ref.pdb")
    scorer = GninaScorer()
    results = {}
    for name in PANEL:
        sdf = os.path.join(ligand_dir, f"{name}.sdf")
        results[name] = scorer.score(receptor, sdf, autobox_ligand=autobox)
    return results


def _main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panel", action="store_true",
                    help="dock+score the AcrR steroid panel")
    ap.add_argument("--receptor", default=None)
    ap.add_argument("--ligand", default=None)
    ap.add_argument("--autobox", default=None)
    args = ap.parse_args()

    if args.panel:
        res = run_panel()
        print(f"{'ligand':14s} {'CNNaffinity':>12s} {'CNNscore':>10s} {'Vina(kcal)':>11s}")
        for name in PANEL:
            r = res[name]
            if "error" in r:
                print(f"{name:14s}  ERROR: {r['error']}")
            else:
                print(f"{name:14s} {r['affinity_pK']:12.3f} {r['pose_score']:10.3f} "
                      f"{r['dG_kcalmol']:11.3f}")
        print("\nWT expectation (LAB_MANUAL §1): testosterone > cortisol > "
              "progesterone; estradiol non-responder.")
        return

    if args.receptor and args.ligand and args.autobox:
        print(GninaScorer().score(args.receptor, args.ligand,
                                  autobox_ligand=args.autobox))
    else:
        ap.error("use --panel, or pass --receptor --ligand --autobox")


if __name__ == "__main__":
    _main()
