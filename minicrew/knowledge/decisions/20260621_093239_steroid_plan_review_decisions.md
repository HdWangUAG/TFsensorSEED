---
title: Decisions — steroid_plan_review
type: decisions
source_run: 20260619_140437_steroid_plan_review
crew: steroid_plan_review
date: 20260621_093239
trust: MEDIUM
---

_Sedimented from discussion run `20260619_140437_steroid_plan_review`._

## Consensus / findings
- **The pose foundation is compromised.** flex-ddG's `_build_complex` reuses pre-posed Boltz coordinates and does not dock; the orientation audit flags ~8/12 WT holo poses as flipped (estradiol 3/3, testosterone 3/3; only progesterone correct). Every pose-based score — clamp geometry, the 3-OH↔carboxylate distance, ΔΔG, the gate — may be measured on a 180°-wrong A-ring. flex-ddG optimizes a given pose; it does not discover a missing binding mode, and tethering can artificially hold decoys in productive poses.
- **flex-ddG margins sit at/below the noise floor.** Current leads (des0002 −1.39, des0007 −1.73; earlier estradiol Top-20 ~−1 to −2 kcal/mol) are at flex-ddG's ~1 kcal/mol best-case resolution. Reported as point values without per-seed CI, they are not rankable as real selectivity.
- **The single R123→Glu/Asp carboxylate clamp is already falsified, not hypothetical.** Empirical scan: R132E (=R123E) gives cortisol 31, estradiol 0.8 (dead) — the carboxylate rewards cortisol's C11/C17/C21 polyol as much as estradiol's phenol. Phenol(donor)-vs-keto(acceptor) discrimination needs a full Glu+Arg+His triad plus explicit cortisol exclusion, not a single anchor.
- **Binding ≠ activation, and activation is where it dies.** 0/20 estradiol leads opened the DBD >38 Å; estradiol binds but won't trigger. The amplitude/activation axis the pipeline defers to "wet-lab" is the axis that already killed every lead.
- **Boltz/Protenix DBD-opening gate is mutation-blind and uncalibrated.** It is a phenotype-inspired binary filter, not an activation free energy; models disagree on opening (des0039 35.3 Å vs Boltz 42.0 Å) and single-structure opening does not predict fluorescence amplitude.
- **Estradiol may be unreachable.** Empirical scan: no single/double mutation unlocks estradiol (max fold-ratio ~2 across 85 mutants), while testosterone>progesterone discrimination is achievable by single D-ring mutations (E106L, L85I, I61L).

## Decisions
- Retrodict known phenotypes with existing instruments before any new design/FEP — owner: computational/modeling — next step: run flex-ddG + 34 Å gate on WT (steroid order), R123E (→cortisol not estradiol), L147R (cortisol switch), F119W, A66M (leak), I61L/L85I (testosterone bias); if the gate can't reproduce these, it cannot gate synthesis.
- Rebuild Tier-1 on SAR-consistent, restrained poses with uncertainty — owner: computational/modeling — next step: anchor A-ring to the correctly-oriented progesterone-style pose, add an orientation filter, run ≥3 seeds/backbones, report median + per-seed spread/bootstrap CI + sign agreement; no flipped-pose score enters a decision.
- Document ligand parameterization provenance — owner: computational — next step: record protonation/tautomer state, partial-charge source, rotatable-bond handling, keto/hydroxyl consistency across the panel, and REU-vs-kcal labelling.
- Run the small decisive wet-lab panel only after retrodiction/pose-rebuild narrow candidates — owner: wet-lab — next step: assay R123E/D ± His/Arg clamp ± cortisol-exclusion + I61L/L85I/E106L controls against all four steroids for binding/EC50 AND induction amplitude.
- Defer Tier-2 FEP until pose/protonation/restraint controls are in place — owner: computational — next step: add fixed pose, fixed protonation, ligand restraints during equilibration, drift cutoff, ≥3 replicates/leg before any RBFE (the controls the E106L run lacked).
- Resolve the target before further spend — owner: PI/strategy — next step: decide estradiol (multi-residue redesign + calibrated activation objective) vs. pivot to testosterone>progesterone discrimination (see open question).

## Open questions
- **Is estradiol still the target?** Given no single/double mutation reaches it (max ratio ~2/85) and 0/20 designs activate, commit to (a) multi-residue estradiol redesign with DBD-activation as a first-class calibrated objective, or (b) pivot to the achievable testosterone>progesterone discrimination. No reviewer or compute run can make this call.
- How were the 35.5 Å / 38 Å gating thresholds set — fitted, transferred, or assumed? A human who knows must confirm before they gate synthesis.
- Do the project's DBD spacing and the literature Y49–Y49′ switch metric (42→39/34 Å, Routh 2009) measure the same thing? Different residue pair and numbers — unverified.
- Can orientation be fixed computationally (SAR-restrained poses) or does it require experimental anchoring? No crystal exists (`AcrR_STR_001.pdb` is itself a Boltz prediction; Boltz pocket-constraint "does NOT work"); co-crystal likely unaffordable, so SAR-restraint is the only tractable lever — but its sufficiency is unproven.
- Does giving decoys equal opportunity (tethered vs weak/no-tether, COM drift/ejection allowance) change the computed selectivity?

## Candidate pitfalls (for human review — not yet a hard rule)
- Do not let any ~1–2 kcal/mol flex-ddG "estradiol selectivity" margin gate synthesis or FEP until poses are orientation-controlled and replicated with uncertainty.
- Do not score poses or build an activation objective on Boltz holo coordinates without an orientation filter — most WT holo poses were flipped.
- Do not treat the 34 Å Boltz-only opening rule as quantitative activation proof; it is mutation-blind and models disagree.
- Do not run production FEP on uncontrolled poses/protonation — the E106L RBFE "converged but was wrong" precisely because pose/drift controls were missing (GIGO).
- Do not let the shared "estradiol selectivity is the goal" framing pass unexamined — reachability itself is the deepest unflagged risk.
- Label Rosetta REU as approximate/relative, not kcal/mol; ligand param details (protonation/charges) "can silently set the answer" for phenol/carboxylate clamp designs.
