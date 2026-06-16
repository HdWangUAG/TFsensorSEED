---
name: tfsensor-dring-campaign
description: TFsensor Stage-3 D-ring steric-clash campaign for testosterone-over-progesterone specificity (bump-and-hole at C17)
metadata: 
  node_type: memory
  type: project
  originSessionId: a8b6a708-ed73-43fe-b948-ff262bc39f09
---

TFsensorSEED testosterone>progesterone specificity campaign (2026-06-15). Strategy = D-ring "bump-and-hole": both steroids share the A-ring 4-en-3-one (read by WT Arg123+Glu106 — PRESERVE these, do NOT design them); they differ only at C17 (testosterone 17β-OH small vs progesterone 20-acetyl bulky). Install bulky hydrophobics at the C17/D-ring shell to clash with progesterone's acetyl but leave room for testosterone's OH.

**D-ring shell identified** (min sidechain dist to progesterone's 20-acetyl, chain A): L85(3.2Å), I61(3.3), W96(3.3, already bulky), L146(3.5), Q88(4.1, kept WT — H-bonds testosterone 17-OH), L147(4.5), L143(5.0), L122(5.3). Design set = **{61,85,122,143,146,147}** both chains; A-ring 123/106 + Q88 + W96 kept WT.

**Pipeline (generalized):** `ligandmpnn_gen.py` now takes `--design_residues`, `--anchor none|123:DE`, `--favor WFI:4.0` (bias_AA_per_residue). `design_score.py panel` takes `--target testosterone --rival progesterone` → ranks by **dG(test)−dG(prog)** (margin<0 = test-specific). Driver: `drive_dring.sh`; scaffold = WT testosterone holo; results in `results/stage3_dring/`.

**How to apply:** screen output `results/stage3_dring/screen.json` (sort_key=margin_vs_rival). Lead designs = most-negative test−prog margin via bulky D-ring substitution. Caveat: closest positions (L85/I61 ~3.2Å) may over-pack and exclude BOTH ligands — let the flex-ddG screen pick variants that selectively exclude only progesterone. See [[tfsensor-stage3-pipeline]], [[tfsensor-numbering-convention]].

## Outcome (2026-06-15)
71 unique D-ring designs → Tier-1 screen ranked by dG(test)−dG(prog). Leads:
- **des0045 = L122I+L146I**: margin **−8.83** (test −31.6, prog −22.8, estr −22.9, cort −23.3) → testosterone the clear best binder over ALL decoys.
- **des0026 = L85W+L146I**: margin **−6.95** (test −27.1, prog −20.1, estr −23.6, cort −19.4) → the Trp "bump" at L85 works; test best.
- des0035 (L85I+L146I): good test−prog (−2.9) BUT estradiol/cortisol bind better (−30/−31) → NOT overall-specific (rejected).
Notable: winning bumps are often **Ile (β-branched), not always Trp** — Trp can over-pack; Ile/Leu→Ile at 122/146 gave the selective squeeze; L85W also worked. L146I recurs in all leads (key position).
**Caveats:** 1-seed/1-relax screen (coarse); des0045's −31.6 test dG is unusually favorable → verify for relax artifact. Leads need Tier-1.5 (34 Å gate: does testosterone still open the switch?) + Tier-2 FEP before trust.


## Validation (3-seed re-score + 34A gate, 2026-06-15)
3-seed ΔΔG: test−prog margins all >=0 → **binding-ΔΔG does NOT robustly resolve test-vs-prog**; the 1-seed leads (des0045 −8.8) were relax ARTIFACTS (dropped out). BUT Tier-1.5 gate: **7/12 pass** — testosterone stays a strong agonist (holo 38-42 A, tight apo), unlike estradiol designs (0/20). Standout **des0039** (holo 42, Δ+8.7). **des0039/des0044/des0060 carry I61L+L85I** = the exact positions the empirical scan validates as test>prog discriminators → gate + wet-lab agree even though binding-ΔΔG is noise-limited. Lesson: test-vs-prog discrimination is functional/efficacy-based; judge by gate + FEP + wet-lab, not binding-ΔΔG margin. Leads: des0039, des0060, des0044 + single E106L. Files: results/stage3_dring/validate/. See [[tfsensor-empirical-scan]].

## 2-ligand gate, ALL 71 designs (2026-06-16)
Re-ran the Tier-1.5 gate **homodimer-correct (2 ligands, one per protomer)** + unbiased (all 71, not just top-12; the old top-12 was picked by the unreliable binding-ΔΔG). Code: `design_gate.py` now has `--all` + `--n_ligand 2`; driver `scripts/gate/drive_gate2lig.sh`; ~8 min/design, ~6.5 h. Result `results/stage3_dring/gate2lig/gate2lig.json`. **Key finding: at 2 ligands the holo opens WIDE for ALL 71 (38.4–49.5 Å, median 44) → agonist criterion (holo>38) is non-discriminating; Boltz over-opens at 2-lig (Protenix gave modest opening). The real discriminator becomes the APO/basal-leak check (apo<35.5; 13 leaky fails).** apo is IDENTICAL 1-vs-2-ligand (apo has no ligand) — only holo changed; the 1-ligand gate's agonist "fails" (des0015/10/52) were false-negatives that open fine at 2-lig. **58/71 pass.** All testosterone leads des0039/44/60/57/18/07/03 pass (tight apo + wide holo). Tightest-apo passers: des0039(33.3), des0009/des0043(33.4). Reinforces: amplitude = wet-lab; the gate's usable signal is the apo leak filter, not the holo amplitude.

## Protenix orthogonal fold (2026-06-15)
Folded leads des0039/des0060 (testosterone+progesterone) with Protenix. ipTM ~0.87-0.89 (folds well, both seat) but flat test≈prog (no specificity, expected). DBD opening on Protenix poses: des0039-test 35.3Å, des0060-test 36.9Å — MUCH smaller than Boltz (42.0/38.1) and flat test≈prog. **Boltz vs Protenix DISAGREE on agonist opening** → the Tier-1.5 gate pass is Boltz-only, NOT cross-predictor-robust; amplitude/opening axis lacks consensus. Trust specificity from empirical scan + ΔΔG/FEP; amplitude = wet-lab. Files: results/stage3_dring/protenix/.