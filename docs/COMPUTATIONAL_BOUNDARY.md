# What the computation CAN and CANNOT do — the evidence-based boundary

_Last updated 2026-06-22. Standing reference for the AcrR steroid-biosensor campaign._

> **One paragraph.** Our computational tools (LigandMPNN, flex-ddG, Boltz two-state gate, FEP, GP/ESM
> surrogates) are reliable for **coarse, large-effect questions** — is this a binder? what is the rough
> WT steroid order? — and for **enumerating** candidate designs. They are **not reliable for the question
> the campaign actually turns on**: ranking *mutation-level selectivity shifts* (which design is more
> testosterone-over-progesterone selective). Three independent methods fail at this, and one (flex-ddG)
> fails with the **wrong sign on every validated lead**. The only trusted selectivity signal is the
> **wet-lab GFP dose-response**. The value of the computation is to **enumerate and to veto obvious
> losers**, not to pick winners.

---

## The boundary, at a glance

| Question | Verdict | Strongest evidence |
|---|---|---|
| Is this a binder / a dead ligand? | ✅ **CAN** (coarse) | #4: estradiol dG −14.95 vs ~−20 for binders; "estradiol opens least in every variant" |
| Rough WT steroid order (big effects) | ✅ **CAN** | #4: dG test(−20.56)<cort(−20.38)<prog(−19.67) = fold 135>104>60 |
| Enumerate candidate multi-mutants | ✅ **CAN** (it's enumeration, not ranking) | LigandMPNN libraries generate fine |
| Qualitative structural rationale (which residue reads the A-ring, SAR) | ✅ **CAN** (hypothesis, not number) | PDBMine recognition code; rescore_oriented SAR filter |
| Get a single steroid's pose/orientation right | ❌ **CANNOT** (reliably) | #4: Boltz flips testosterone A-ring **14/15**; prog 3/15 |
| Rank designs by **mutation-level selectivity** | ❌ **CANNOT** | P1 GP Spearman ≤0; #4 flex-ddG **wrong sign 3/3**; ranker ≈ chance |
| Predict allosteric **amplitude / sensor quality** | ❌ **CANNOT** | two-state opening vs fluorescence: Spearman −0.2; ~0.5 Å signal under several-Å noise |
| Use the 35.5/38 Å gate as a **quantitative** filter | ❌ **CANNOT** | Boltz-self-derived heuristic (resolved 2026-06-22); over-opens; circular on its own outputs |
| FEP as a **screening** selectivity oracle | ❌ **CANNOT** (case-by-case at best) | 1 success (L147R) vs 1 GIGO (E106L); too costly; pose-sensitive |

---

## Evidence ledger — read this before trusting any "computation agrees with experiment"

The recurring trap: a result "looks supportive" when checked **loosely, in-sample, or on a big effect**.
The same tool fails when checked **rigorously, blind, on the subtle effects design actually needs.** Each
row notes the *kind* of evidence so the claim isn't over-read.

### Evidence that computation CAN do the coarse things
- **WT steroid order recovered (#4, controlled).** flex-ddG on orientation-corrected poses reproduced
  test<cort<prog and estradiol weakest. *Strength: real and repeatable — but it is a large, above-noise
  effect (binder vs non-binder spans ~5.6 kcal/mol).*
- **Estradiol = dead binder, every variant.** Both the two-state opening work and #4 agree estradiol is
  the weakest. *Strength: the one robust discriminator; safe as a dead-binder gate.*
- **FEP plumbing validated (L147R×cortisol).** ΔΔG_bind −8.6 kJ/mol (BAR), sign-correct. *Strength: a
  retrospective DEMO on a KNOWN, dramatic switch — it validates the pipeline mechanics, NOT blind
  predictive power. You already knew the answer.*

### Evidence that computation CANNOT do the thing we need (mutation-level selectivity)
- **Supervised ranker:** held-out pairwise accuracy ≈ 0.50 (chance).
- **P1 grouped-CV (GP surrogate), 2026-06-22:** leave-one-position-out Spearman ≤0 for physchem/ESM/concat
  (testosterone −0.26/−0.14/−0.10; cortisol −0.58/+0.02/+0.05); a trivial additive baseline beats every GP;
  known leads not rediscovered.
- **#4 flex-ddG on orientation-corrected poses, 2026-06-22:** the testosterone-selectivity shift
  `(dG_test−dG_prog)_mut − (…)_WT` was the **wrong sign for all three validated singles** — I61L +4.31,
  L85I +2.45, E106L +1.93 kcal/mol (negative = correct). Empirically all three *raise* the test/prog fold
  ratio (2.26 → 7.24 / 8.78 / 4.68).
- **E106L specificity FEP:** converged but disagreed with the assay — GIGO from a wrong pose / second-shell
  target.

**Why these two buckets are consistent, not contradictory:** the "CAN" cases are large effects, demos on
known answers, or in-sample; the "CANNOT" cases are blind, sign-tracking tests on the temperate
mutation-level shifts that matter. The dividing line is **effect size relative to the ~1 kcal/mol ΔΔΔG
noise floor**, plus **pose reliability** (the target's A-ring is right only 7% of the time).

### Also note: FEP ≠ flex-ddG
The one blind-ish success (L147R) used **FEP (Tier-2, expensive)**; the #4 failure used **flex-ddG
(Tier-1, the cheap pre-filter)**. So "computation once agreed" partly means "an expensive method got one big
switch right." Even FEP's record is 1 win / 1 GIGO — not a track record to gate a campaign on, and far too
costly to screen broadly.

---

## Practical guide — USE the tools for this, DO NOT for that

### ✅ DO use computation to:
1. **Veto obvious non-binders** — the dead-binder gate (estradiol-style). Coarse pass/fail only.
2. **Enumerate** candidate multi-mutant libraries (LigandMPNN) to define the design space.
3. **Sanity-check coarse, WT-like ordering** (a smoke test, not a ranking).
4. **Generate structural hypotheses / SAR rationale** — which residues contact the A-ring, orientation
   filtering — as *qualitative* guidance to design wet-lab panels.
5. **Validate pipeline mechanics** retrospectively on known switches before trusting any new run.

### ❌ DO NOT use computation to:
1. **Rank designs by selectivity or pick "the winner."** Three methods fail; flex-ddG fails wrong-signed.
2. **Predict sensor amplitude / dynamic range / sensor quality** — allostery ≠ binding; it is a wet-lab
   readout, full stop.
3. **Gate synthesis on a ~1–2 kcal/mol ΔΔΔG margin or on an Å-gate number.** Below the noise floor /
   self-derived heuristic.
4. **Trust a single predicted pose's orientation** — fold multiple seeds and SAR-filter; expect most poses
   wrong for testosterone.
5. **Read "passes the gate" as "experimentally selective."** It is not validation.

---

## The one trusted signal
**Wet-lab GFP fold-induction, dose-response (basal / amplitude / EC50 / Hill), with replicate variance.**
Selectivity and amplitude decisions are made here — not by any surrogate, ΔΔG, gate, or pose. The next
concrete step is the **round-1 dose-response diagnostic** (`results/stage4_bo/round1_diagnostic.md`,
regenerate via `tfsensor/ml/bo/round1_design.py`).

## Is the boundary permanent?
No — it is "with current tools, data, and cost." It could move only with: (a) experimentally-correct
poses (a crystal structure, or far more co-folds), (b) enhanced-sampling MD (drMD-tier) for amplitude,
or (c) enough *multi-mutant dose-response* data to fit a data-driven model. Until one of those exists,
treat the boundary above as binding.
