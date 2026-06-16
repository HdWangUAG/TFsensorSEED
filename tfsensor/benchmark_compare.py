"""Stage-1d cross-variant benchmark: do the pipelines recapitulate the mutant data?

Loads the per-variant evaluation JSONs (WT / F119W / L147R) produced by the
analysis driver and assembles a ligand x variant table for each computational
axis, plus the change vs WT. Then it checks the specific experimental
expectations the wet-lab data sets out:

  F119W (sensitivity amplifier):
    * Test/Prog affinity BOOST   -> dG more negative than WT (ddG < 0), bp up
    * Cortisol gains response     -> dG lower & opening/coupled up vs WT cortisol
  L147R (specificity switch):
    * Cortisol becomes favored    -> strong dG / coupled, ideally best in-variant
    * Testosterone penalized      -> dG less favorable than WT test (ddG > 0), down
    * Amplitude attenuation       -> max DBD opening < WT testosterone opening

Axes: Boltz binder-prob (bind, higher=stronger), Protenix ligand-ipTM (bind,
higher), Rosetta dG_separated (bind, LOWER=stronger), DBD opening (switch,
higher=more derepression), coupled biosensor score (higher=more signal).

    python -m tfsensor.benchmark_compare --root results/stage1d_mutants \
        --mutants data/mutants.json --out_json results/stage1d_mutants/BENCHMARK.json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics

VARIANTS = ["wt", "f119w", "l147r"]
LIGANDS = ["testosterone", "progesterone", "cortisol", "estradiol"]


def _mean_scores(path):
    """scores[seed][lig] -> mean per lig (Boltz/Protenix go_nogo layout)."""
    if not os.path.exists(path):
        return {}
    d = json.load(open(path))
    scores = d.get("scores", {})
    out = {}
    for lig in LIGANDS:
        vals = [s[lig] for s in scores.values() if lig in s]
        if vals:
            out[lig] = round(statistics.mean(vals), 4)
    return out


def _load_variant(rdir):
    v = {}
    v["bp"] = _mean_scores(os.path.join(rdir, "boltz_go_nogo.json"))
    v["iptm"] = _mean_scores(os.path.join(rdir, "protenix_go_nogo.json"))
    p = os.path.join(rdir, "physics_go_nogo.json")
    v["dG"] = json.load(open(p)).get("mean_dG_per_ligand", {}) if os.path.exists(p) else {}
    t = os.path.join(rdir, "trigger_go_nogo.json")
    if os.path.exists(t):
        td = json.load(open(t))
        v["opening"] = td.get("mean_opening_per_ligand", {})
        v["apo_dbd"] = td.get("apo_dbd")
    else:
        v["opening"] = {}
    b = os.path.join(rdir, "biosensor_score.json")
    if os.path.exists(b):
        bd = json.load(open(b))
        v["coupled"] = {k: r["biosensor_score"] for k, r in bd.get("per_ligand", {}).items()}
    else:
        v["coupled"] = {}
    return v


def _fmt(x, nd=2):
    return f"{x:.{nd}f}" if isinstance(x, (int, float)) else " . "


def _table(data, axis, nd=2):
    lines = [f"  {'ligand':13s} {'WT':>9s} {'F119W':>9s} {'L147R':>9s}"
             f" {'dMut(F)':>9s} {'dMut(L)':>9s}"]
    for lig in LIGANDS:
        wt = data["wt"][axis].get(lig)
        fm = data["f119w"][axis].get(lig)
        lm = data["l147r"][axis].get(lig)
        df = round(fm - wt, 2) if (wt is not None and fm is not None) else None
        dl = round(lm - wt, 2) if (wt is not None and lm is not None) else None
        lines.append(f"  {lig:13s} {_fmt(wt,nd):>9s} {_fmt(fm,nd):>9s} {_fmt(lm,nd):>9s}"
                     f" {_fmt(df,nd):>9s} {_fmt(dl,nd):>9s}")
    return "\n".join(lines)


def _check(label, ok, detail):
    mark = "PASS" if ok else ("FAIL" if ok is False else "n/a ")
    return f"  [{mark}] {label}: {detail}"


def run(root, out_json):
    data = {v: _load_variant(os.path.join(root, v)) for v in VARIANTS}

    out = {"variants": data, "checks": {}}
    rep = []
    rep.append("============ STAGE-1d MUTANT BENCHMARK (computational recapitulation) ============")
    rep.append("Experimental ground truth encoded in data/mutants.json. dMut = mutant - WT.\n")

    rep.append("---- AXIS: Boltz binder-prob (binding; higher = stronger) ----")
    rep.append(_table(data, "bp", 3))
    rep.append("\n---- AXIS: Protenix ligand-ipTM (binding; higher = stronger) ----")
    rep.append(_table(data, "iptm", 3))
    rep.append("\n---- AXIS: Rosetta dG_separated (binding; LOWER = stronger) ----")
    rep.append(_table(data, "dG", 2))
    rep.append("\n---- AXIS: DBD opening holo-apo (switch; higher = more signal) ----")
    rep.append(_table(data, "opening", 2))
    rep.append("\n---- AXIS: coupled biosensor score P(bound)*max(open,0) ----")
    rep.append(_table(data, "coupled", 3))

    # ---------- targeted experimental checks ----------
    def g(v, axis, lig):
        return data[v][axis].get(lig)

    checks = []
    rep.append("\n============ EXPERIMENTAL EXPECTATION CHECKS ============")

    # F119W: Test/Prog affinity boost -> dG more negative than WT
    for lig in ("testosterone", "progesterone"):
        wt, fm = g("wt", "dG", lig), g("f119w", "dG", lig)
        ok = (wt is not None and fm is not None and fm < wt)
        out["checks"][f"F119W_{lig}_dG_boost"] = ok
        rep.append(_check(f"F119W {lig} dG boost (more negative than WT)", ok,
                          f"WT {_fmt(wt)} -> F119W {_fmt(fm)} (ddG {_fmt((fm-wt) if (wt is not None and fm is not None) else None)})"))
    # F119W: Cortisol gains response -> dG lower AND coupled up vs WT cortisol
    wt_c_dg, fm_c_dg = g("wt", "dG", "cortisol"), g("f119w", "dG", "cortisol")
    wt_c_cp, fm_c_cp = g("wt", "coupled", "cortisol"), g("f119w", "coupled", "cortisol")
    ok = (wt_c_dg is not None and fm_c_dg is not None and fm_c_dg < wt_c_dg)
    out["checks"]["F119W_cortisol_dG_gain"] = ok
    rep.append(_check("F119W cortisol binding gain (dG lower than WT)", ok,
                      f"WT {_fmt(wt_c_dg)} -> F119W {_fmt(fm_c_dg)}"))
    ok2 = (wt_c_cp is not None and fm_c_cp is not None and fm_c_cp > wt_c_cp)
    out["checks"]["F119W_cortisol_coupled_gain"] = ok2
    rep.append(_check("F119W cortisol response gain (coupled up vs WT)", ok2,
                      f"WT {_fmt(wt_c_cp,3)} -> F119W {_fmt(fm_c_cp,3)}"))

    # L147R: Testosterone penalized -> dG less favorable than WT test (ddG > 0)
    wt_t, lm_t = g("wt", "dG", "testosterone"), g("l147r", "dG", "testosterone")
    ok = (wt_t is not None and lm_t is not None and lm_t > wt_t)
    out["checks"]["L147R_testosterone_penalized_dG"] = ok
    rep.append(_check("L147R testosterone penalized (dG less favorable than WT)", ok,
                      f"WT {_fmt(wt_t)} -> L147R {_fmt(lm_t)} (ddG {_fmt((lm_t-wt_t) if (wt_t is not None and lm_t is not None) else None)})"))
    # L147R: testosterone signal down (coupled & opening down vs WT)
    wt_t_cp, lm_t_cp = g("wt", "coupled", "testosterone"), g("l147r", "coupled", "testosterone")
    ok = (wt_t_cp is not None and lm_t_cp is not None and lm_t_cp < wt_t_cp)
    out["checks"]["L147R_testosterone_signal_down"] = ok
    rep.append(_check("L147R testosterone signal down (coupled < WT)", ok,
                      f"WT {_fmt(wt_t_cp,3)} -> L147R {_fmt(lm_t_cp,3)}"))
    # L147R: Cortisol becomes a (the) responder -> cortisol coupled is best in L147R
    lm_cp = data["l147r"]["coupled"]
    if lm_cp:
        best = max(lm_cp, key=lm_cp.get)
        ok = (best == "cortisol")
        out["checks"]["L147R_cortisol_is_top_responder"] = ok
        rep.append(_check("L147R cortisol is top responder (coupled)", ok,
                          f"top = {best} ({_fmt(lm_cp.get(best),3)}); cortisol {_fmt(lm_cp.get('cortisol'),3)}"))
        # cortisol favored over testosterone (the inversion)
        ok2 = (lm_cp.get("cortisol") is not None and lm_cp.get("testosterone") is not None
               and lm_cp["cortisol"] > lm_cp["testosterone"])
        out["checks"]["L147R_cortisol_over_testosterone"] = ok2
        rep.append(_check("L147R specificity inversion (cortisol > testosterone, coupled)", ok2,
                          f"cort {_fmt(lm_cp.get('cortisol'),3)} vs test {_fmt(lm_cp.get('testosterone'),3)}"))
    # L147R: amplitude attenuation -> max opening < WT testosterone opening
    wt_t_open = g("wt", "opening", "testosterone")
    lm_open = data["l147r"]["opening"]
    if lm_open and wt_t_open is not None:
        lm_max = max(lm_open.values())
        ok = (lm_max < wt_t_open)
        out["checks"]["L147R_amplitude_attenuated"] = ok
        rep.append(_check("L147R amplitude attenuated (max opening < WT testosterone)", ok,
                          f"L147R max opening {_fmt(lm_max)} vs WT test {_fmt(wt_t_open)}"))

    npass = sum(1 for v in out["checks"].values() if v is True)
    ntot = len(out["checks"])
    rep.append(f"\nSUMMARY: {npass}/{ntot} experimental expectations recapitulated.")

    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    json.dump(out, open(out_json, "w"), indent=2)
    print("\n".join(rep))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="results/stage1d_mutants")
    ap.add_argument("--mutants", default="data/mutants.json")
    ap.add_argument("--out_json", required=True)
    args = ap.parse_args()
    run(args.root, args.out_json)


if __name__ == "__main__":
    main()
