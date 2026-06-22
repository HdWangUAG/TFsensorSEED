---
title: Decisions — bo_plan_review
type: decisions
source_run: 20260622_132256_bo_plan_review
crew: bo_plan_review
date: 20260622_134637
trust: MEDIUM
---

_Sedimented from discussion run `20260622_132256_bo_plan_review`._

## Consensus / findings
- **Singles → multi-mutant extrapolation is the central, unvalidated risk.** Seed is ~84 single mutants; BO targets combinatorial multi-mutants. ESM embedding smoothness can make k≥2 designs look *confidently* interpolated; epistasis is unobserved. The GP must show high posterior variance for k≥2 designs far from singles, not confident rankings.
- **The objective is built on the wrong readout granularity.** `y1`/`y2` derive from single-dose GFP fold-induction, which misranks selectivity (operating ranges differ per variant — WT 1–100 µM vs L147R 1–5 µM) and conflates basal leak with induction (A66M reads 130,097 basal = fake signal). Replicate variance is not propagated, so GP noise is misspecified.
- **The in-silico pre-filter inherits compromised poses.** ~8/12 WT holo poses are A-ring-flipped (`ORIENTATION_WARNING`), so any clamp/ΔΔG distance may be 180° wrong. The funnel's filters (GP, flex-ddG, Boltz, LigandMPNN, ESM) reuse the same structural prior, so stacking may amplify shared error rather than de-risk.
- **Features encode pocket binding chemistry only; the objective is bind × allosteric trigger.** There is no coordinate for apo→holo DBD opening — the axis that killed every prior lead (0/20 estradiol designs activated). Mean-pooling 14 pocket residues to ~1280-dim destroys the H-bond directionality/geometry (phenol-donor vs 3-keto-acceptor; carboxylate-clamp) that *is* the specificity.
- **Wet-lab controls are missing.** Need WT anchor, no-ligand basal, validated positive (E106L/L85I/I61L/R123E) + non-responder (estradiol), ≥3 biological replicates, and exploration/random wells — else BO chases plate noise.
- **The plan omits q, #rounds, and build method.** Multi-mutant builds need multi-primer assembly or gene synthesis (~$80–200/construct, 1–2 wk lead); realistic ceiling ~20–48 verified multi-mutants/round at 3–5 weeks each.

## Decisions
- Run a retrospective grouped-CV benchmark (leave-one-position-out + leave-one-chemical-class-out) on the 84 singles BEFORE anything else — owner: ML/Stats — next step: require rediscovery of E106L/L85I/I61L/R123E, top-k enrichment over additive+random baselines, calibrated 80/95% coverage; if it fails, do not rank multi-mutants.
- Ablate the feature set (additive vs one-hot vs physchem-only vs ESM-only vs concat) in the same harness — owner: ML/Stats — next step: keep ESM only if it beats additive.
- Fix the pre-filter pose foundation — owner: Structural/Computational — next step: SAR-restrain A-ring to the correct (progesterone-style) pose, add orientation filter, report per-seed median + spread; either add a separately-measured activation descriptor or drop y2 as a predicted objective and label amplitude wet-lab-only.
- Specify and right-size the loop — owner: HTS/Computational — next step: set ≤3 rounds, q≈24–32 against real throughput; feed round-0 replicate variance as heteroscedastic GP noise.
- Run one decisive, fully-controlled round-1: dose-response (EC50 + amplitude) on validated-singles doubles (I61L+L85I, I61L+Q88T) plus the singles, all four steroids, full control set — owner: Wet-lab/HTS — next step: measure epistasis and assay noise directly before any BO-proposed combinatorial designs.
- Defer Tier-2 FEP — owner: Computational — next step: no FEP spend until poses/protonation/restraints/drift-cutoff/≥3 replicates are in place.

## Open questions
- **Target steroid commitment (human-only call):** estradiol (requires multi-residue redesign *and* an explicit separately-measured DBD-activation objective; 0/20 prior leads activated) vs pivot to achievable testosterone>progesterone discrimination (first-shell D-ring, validated by single mutations). Every must-fix is conditioned on this.
- **Is GFP fold-induction (bind × allosteric trigger) learnable at all from a pocket-sequence binding-feature surrogate?** Load-bearing assumption under the entire surrogate; Structural says no (opening ~0.5 Å signal vs several-Å noise, wet-lab only), plan assumes yes. Unresolved in the record — retrospective benchmark is the cheapest exposure.
- **Provenance of the 35.5 Å / 38 Å gate thresholds** — fitted, transferred, or assumed? Whether they correspond to the literature Y49–Y49′ switch metric. A human who set them must confirm.
- Whether the multi-model funnel's filters are genuinely independent — needs measured pairwise rank correlations among GP mean, acquisition score, flex-ddG margin, Boltz apo/holo, LigandMPNN likelihood vs known GFP outcomes.
- λ and the EPS=1.0 floor in the objective definitions need sensitivity analysis / bootstrap from replicate GFP errors.

## Candidate pitfalls (for human review — not yet a hard rule)
- Don't let "the wet-lab readout is trusted" smuggle in "the readout *as formatted into y1/y2* is trusted" — single-dose fold-induction itself misranks and conflates leak.
- Don't score binding features against an activation objective without a coordinate for the apo→holo population shift — it repeats the 0/20-activation failure mode in silico.
- Don't gate candidates with flex-ddG/Boltz scores derived from flipped (A-ring 180°) poses.
- Don't treat singles→multi-mutant as "de-risked, not removed" without measuring epistasis directly first.
- Don't run a long active-learning drip (q=8–16) that the wet-lab calendar can't sustain; size batches for information against real throughput.
