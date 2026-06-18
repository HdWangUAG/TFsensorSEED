# AcrR Progesterone & Cortisol Biosensor — Designs for Wet-Lab Testing

**Prepared:** 2026-06-17 · **Targets:** progesterone-selective and cortisol-selective derepression (GFP) over the other steroids. Companion to the testosterone sheet.

AcrR is a TetR-family homodimeric repressor; ligand binding opens the DNA-binding domains and derepresses GFP. Each design is a **single AcrR monomer** (182 aa); the sensor is the homodimer (two identical copies). Sequences are drop-in replacements for wild-type AcrR.

## How to read this sheet

- **Mutations** in two schemes: *model* = position in the 182-aa sequence (1-based); *experimental* = model + 9 (your prior assay numbering).
- **dG** = relative PyRosetta flex-ddG scores (kcal/mol, lower = tighter) — coarse guide only.
- **Gate** = 2-ligand Boltz DBD opening (Å): apo < 35.5 (non-leaky) · holo > 38 (agonist).

## Priority for testing

**Progesterone**
1. **des0002** (I61L, Q88T) — primary; Q88T reads progesterone's C20 acetyl; passes gate.
2. **des0000** (I61L, Q88L) — backup; passes gate.

**Cortisol**
1. **R123E** (single) — wet-lab validated cortisol switch; best positive control.
2. **des0001** (I61V, Q88L, R123E) — only gate-clean multi-site cortisol design.
3. **des0007** (I61L, Q88T, R123E) — most selective by score but predicted **leaky** (higher-risk).

## Design summary

| ID | target | tier | mutations (model) | mutations (exp) | apo Å | holo Å | gate |
|---|---|---|---|---|---|---|---|
| WT_AcrR | — | reference | — | — | — | — | — |
| des0002 | progesterone | prog primary | I61L; Q88T | I70L; Q97T | 35.408 | 40.819 | PASS |
| des0000 | progesterone | prog backup | I61L; Q88L | I70L; Q97L | 33.708 | 40.028 | PASS |
| des0001 | cortisol | cort primary (gate-clean) | I61V; Q88L; R123E | I70V; Q97L; R132E | 34.91 | 41.065 | PASS |
| des0007 | cortisol | cort alternate (leaky-risk) | I61L; Q88T; R123E | I70L; Q97T; R132E | 36.986 | 40.164 | leaky |
| R123E | cortisol | validated single-mut | R123E | R132E | — | — | — |

## Expected phenotype

- **Progesterone designs:** respond to **progesterone** > testosterone / cortisol / estradiol.
- **Cortisol designs:** respond to **cortisol** > the others (R123E is the validated anchor).
WT baseline (assay): testosterone 135, progesterone 60, cortisol 104, estradiol 0.8. Suggested readout: GFP dose-response for **all four steroids**.

## FASTA sequences (monomer, 182 aa)

```
>WT_AcrR  | wild type
MPGRGGILDAATRLFATHGVSGTSLQQIAGAAGITKAAVYHHFPTKEEVVAAVLAPALEA
IDALVRTAEAHDEPRTRTEAAIIGLADQAVTHRQRWAVLLQDAAVEEYIRNDPGHDELFT
RLRGLLTGPGPDPGTRLQVALFLSGLLGPAQDPSCADIDDDDLRAGIVRAGRLLLLDGAA
TG
>des0002  | target: progesterone | mut(model): I61L; Q88T | mut(exp): I70L; Q97T
MPGRGGILDAATRLFATHGVSGTSLQQIAGAAGITKAAVYHHFPTKEEVVAAVLAPALEA
LDALVRTAEAHDEPRTRTEAAIIGLADTAVTHRQRWAVLLQDAAVEEYIRNDPGHDELFT
RLRGLLTGPGPDPGTRLQVALFLSGLLGPAQDPSCADIDDDDLRAGIVRAGRLLLLDGAA
TG
>des0000  | target: progesterone | mut(model): I61L; Q88L | mut(exp): I70L; Q97L
MPGRGGILDAATRLFATHGVSGTSLQQIAGAAGITKAAVYHHFPTKEEVVAAVLAPALEA
LDALVRTAEAHDEPRTRTEAAIIGLADLAVTHRQRWAVLLQDAAVEEYIRNDPGHDELFT
RLRGLLTGPGPDPGTRLQVALFLSGLLGPAQDPSCADIDDDDLRAGIVRAGRLLLLDGAA
TG
>des0001  | target: cortisol | mut(model): I61V; Q88L; R123E | mut(exp): I70V; Q97L; R132E
MPGRGGILDAATRLFATHGVSGTSLQQIAGAAGITKAAVYHHFPTKEEVVAAVLAPALEA
VDALVRTAEAHDEPRTRTEAAIIGLADLAVTHRQRWAVLLQDAAVEEYIRNDPGHDELFT
RLEGLLTGPGPDPGTRLQVALFLSGLLGPAQDPSCADIDDDDLRAGIVRAGRLLLLDGAA
TG
>des0007  | target: cortisol | mut(model): I61L; Q88T; R123E | mut(exp): I70L; Q97T; R132E
MPGRGGILDAATRLFATHGVSGTSLQQIAGAAGITKAAVYHHFPTKEEVVAAVLAPALEA
LDALVRTAEAHDEPRTRTEAAIIGLADTAVTHRQRWAVLLQDAAVEEYIRNDPGHDELFT
RLEGLLTGPGPDPGTRLQVALFLSGLLGPAQDPSCADIDDDDLRAGIVRAGRLLLLDGAA
TG
>R123E  | target: cortisol | mut(model): R123E | mut(exp): R132E
MPGRGGILDAATRLFATHGVSGTSLQQIAGAAGITKAAVYHHFPTKEEVVAAVLAPALEA
IDALVRTAEAHDEPRTRTEAAIIGLADQAVTHRQRWAVLLQDAAVEEYIRNDPGHDELFT
RLEGLLTGPGPDPGTRLQVALFLSGLLGPAQDPSCADIDDDDLRAGIVRAGRLLLLDGAA
TG
```

## Important caveats (please read)

- **Computational designs.** Only **R123E** has direct wet-lab support (cortisol). The multi-site designs are predictions needing experimental confirmation.
- **dG cannot resolve ~1 kcal/mol selectivity** — leads chosen by gate + design logic + (for R123E) the assay, not the margin alone.
- **Gate is a single-predictor structural proxy**; predicted amplitude is a hypothesis — measure it.
- **Binding-pose orientation is unreliable.** Progesterone poses are SAR-consistent (3-keto→R123 ~3 Å), but cortisol poses are NOT (3-keto buried ~12 Å) and could not be corrected even with constrained re-folding. So the cortisol structural rationale rests on the **validated R123E + chemical logic**, not the predicted pose.
- **Cortisol selectivity-vs-leakiness tension:** the most cortisol-selective designs (e.g. des0007, polar Q88T) tend to be predicted leaky; des0001 trades some selectivity for a non-leaky apo.


*Machine-readable companion: `AcrR_prog_cort_sensor_designs.csv` (+ full dG columns + sequences). Testosterone designs: `AcrR_testosterone_sensor_designs.{md,csv}`.*
