#!/usr/bin/env python3
"""Analyze the E106L specificity campaign and write SPECIFICITY_RESULTS.md.

Per ligand we have dG_bound(WT->E106L); apo gives dG_apo. Then:
  dDG_bind(L)   = dG_bound(L) - dG_apo            # effect of E106L on L's binding
  S(comp)       = dDG_bind(comp) - dDG_bind(test) # = dG_bound(comp) - dG_bound(test)
                                                  #   (apo cancels) -> selectivity shift
S(comp) > 0  =>  E106L disfavors `comp` relative to testosterone (testosterone-selective).
Compared against the wet-lab fold-induction for E106L vs WT.
"""
import math, os, re

CAMP = os.path.dirname(os.path.abspath(__file__))
KJ = 4.184
LIGS = ["testosterone", "progesterone", "cortisol", "estradiol"]

# Wet-lab fold-induction (GFP), model numbering, from EMPIRICAL_SCAN_SUMMARY.md
ASSAY_WT    = {"testosterone": 135, "progesterone": 60,  "cortisol": 104, "estradiol": 0.8}
ASSAY_E106L = {"testosterone": 26,  "progesterone": 5.6, "cortisol": 1.8, "estradiol": 0.6}


def read_leg(tag):
    f = os.path.join(CAMP, "work", tag, f"results_{tag}.dat")
    if not os.path.exists(f):
        return None
    t = open(f).read()
    def g(p):
        m = re.search(p, t)
        return float(m.group(1)) if m else None
    return {"BAR": g(r"BAR: dG\s*=\s*(-?[\d.]+)"),
            "BAR_e": g(r"BAR: Std Err \(bootstrap\)\s*=\s*([\d.]+)"),
            "CGI": g(r"CGI: dG\s*=\s*(-?[\d.]+)"),
            "CGI_e": g(r"CGI: Std Err \(bootstrap\)\s*=\s*([\d.]+)")}


def main():
    legs = {tag: read_leg(tag) for tag in LIGS + ["apo"]}
    have = {k: v for k, v in legs.items() if v}
    apo = legs.get("apo")
    lines = []
    P = lines.append

    P("# E106L — testosterone-specificity FEP validation\n")
    P(f"**Campaign:** `results/stage3_fep/e106l_specificity/` · "
      f"mutation **E106L** (both chains) · pmx + GROMACS non-eq TI (BAR).\n")
    P("Protein-mutation RBFE in each ligand-bound complex (+ apo). The ligand is never "
      "alchemically changed, so estradiol's aromatic A-ring poses no mapping problem.\n")

    missing = [t for t in LIGS + ["apo"] if not legs.get(t)]
    if missing:
        P(f"> ⚠️ legs not finished / failed: {', '.join(missing)}\n")

    # --- raw dG per leg ---
    P("\n## 1. Raw alchemical dG(WT→E106L) per leg (kJ/mol)\n")
    P("| leg | BAR dG | ±boot | CGI dG |")
    P("|---|---|---|---|")
    for tag in LIGS + ["apo"]:
        r = legs.get(tag)
        if r:
            P(f"| {tag} | {r['BAR']:.1f} | {r['BAR_e']:.1f} | {r['CGI']:.1f} |")
        else:
            P(f"| {tag} | — | — | — |")

    # --- dDG_bind per ligand (needs apo) ---
    if apo:
        P("\n## 2. ΔΔG_bind(E106L) per ligand = dG_bound − dG_apo (kJ/mol)\n")
        P("Sign: <0 = E106L strengthens that ligand's binding; >0 = weakens it.\n")
        P("| ligand | ΔΔG_bind | ± | kcal/mol |")
        P("|---|---|---|---|")
        for lig in LIGS:
            r = legs.get(lig)
            if not r:
                P(f"| {lig} | — | — | — |"); continue
            dd = r["BAR"] - apo["BAR"]
            e = math.hypot(r["BAR_e"], apo["BAR_e"])
            P(f"| {lig} | {dd:+.1f} | {e:.1f} | {dd/KJ:+.2f} |")

    # --- specificity double-difference (apo cancels) ---
    test = legs.get("testosterone")
    if test:
        P("\n## 3. Selectivity shift S(comp) = dG_bound(comp) − dG_bound(testosterone)\n")
        P("**S > 0 ⟹ E106L disfavors the competitor relative to testosterone "
          "(testosterone-selective shift).** Apo cancels exactly here.\n")
        P("| competitor | S (kJ/mol) | ± | S (kcal/mol) | direction |")
        P("|---|---|---|---|---|")
        for comp in ["progesterone", "cortisol", "estradiol"]:
            r = legs.get(comp)
            if not r:
                P(f"| {comp} | — | — | — | — |"); continue
            s = r["BAR"] - test["BAR"]
            e = math.hypot(r["BAR_e"], test["BAR_e"])
            verdict = ("✅ test-selective" if s - e > 0 else
                       "❌ favors competitor" if s + e < 0 else
                       "≈ within error")
            P(f"| {comp} | {s:+.1f} | {e:.1f} | {s/KJ:+.2f} | {verdict} |")

    # --- vs wet-lab ---
    P("\n## 4. Comparison to wet-lab (E106L GFP fold-induction)\n")
    P("Assay E106L: " + ", ".join(f"{k} {ASSAY_E106L[k]}" for k in LIGS) +
      " (WT: " + ", ".join(f"{k} {ASSAY_WT[k]}" for k in LIGS) + ").\n")
    P("Assay says E106L stays testosterone-responsive while cortisol & progesterone "
      "collapse and estradiol is dead — i.e. cortisol should be the *most* disfavored. "
      "FEP agrees if S(cortisol) and S(progesterone) are positive (cortisol largest).\n")

    out = os.path.join(CAMP, "SPECIFICITY_RESULTS.md")
    open(out, "w").write("\n".join(lines) + "\n")
    print("wrote", out)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
