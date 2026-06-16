---
name: tfsensor-empirical-scan
description: TFsensor empirical 85-mutant×20-ligand GFP scan — validates ΔΔG (R123E→cortisol), estradiol unreachable by point mutation, E106L/L85I/I61L = testosterone-specific
metadata:
  type: project
---

Empirical AcrR mutation scan (`experimental_data/emperical_mutations/202512.21AcrR突变.xlsx`; 11 GFP plates, **85 single mutants × ~20 ligands**, fold-induction ratio). Parsed → `results/stage1f_empirical/scan_model_numbering.csv` + `EMPIRICAL_SCAN_SUMMARY.md`. **File uses EXPERIMENTAL numbering; model = experimental − 9** (confirmed: F128W=F119W, R132=R123, E115=E106).

**Key learnings:** (1) WT responds testosterone135>cortisol104>prog60>DHT51, **estradiol 0.8 (dead)**. (2) **R132E = our R123E estradiol anchor FAILS for estradiol** (estr 0.8) and goes to **cortisol (31)** — EXACTLY our Stage-3 flex-ddG prediction → pipeline validated; drop single R123E for estradiol. (3) **No single/double mutation unlocks estradiol** (max ratio ~2 across all 85) → estradiol needs multi-residue redesign (weak agonist; hard target). (4) **Testosterone-over-progesterone IS achievable by single muts, several at OUR D-ring positions**: **E106L** (test26/prog5.6/cort1.8 — clean test-selective), **L85I** (test120/prog13.7 — kills prog; our des0035 direction), **I61L** (test21/prog2.9); also S154R, I167L, C155L → validates the D-ring bump-and-hole. (5) **F119W** = broad amplifier (all 4-en-3-ones↑, estradiol dead). (6) Hyperactive/leaky class (D116*, T91D ~1000×, R95L, R64K, H115*, V139A) = sensitivity/leak knob, not specificity.

**How to apply:** fold **E106L, L85I, I61L** into the testosterone D-ring panel and re-screen; treat estradiol as multi-residue/FEP-only; use R123E result as the calibration anchor (computation matched experiment). See [[tfsensor-dring-campaign]], [[tfsensor-ddg-calibration]], [[tfsensor-numbering-convention]].
