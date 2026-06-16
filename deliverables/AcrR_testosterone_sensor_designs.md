# AcrR Testosterone Biosensor — Designs for Wet-Lab Testing

**Prepared:** 2026-06-16  ·  **Target:** testosterone-selective derepression (GFP fold-induction) over progesterone, cortisol, estradiol.

AcrR is a TetR-family homodimeric repressor; ligand binding opens the DNA-binding domains and derepresses the GFP reporter. Each design below is a **single AcrR monomer** (182 aa); the functional sensor is the homodimer (two identical copies). Sequences are drop-in replacements for wild-type AcrR.

## How to read this sheet

- **Mutations** are given in two numbering schemes:
  - *model* = position in the 182-aa sequence below (1-based) — use this to locate the residue in the FASTA.
  - *experimental* = model + 9 — matches the numbering of your prior AcrR assay data.
- **dG** columns are *relative* PyRosetta flex-ddG binding scores (kcal/mol, lower = tighter). Use them only as a coarse guide (see caveats).
- **Gate** columns are the predicted DNA-binding-domain opening (Å): a tight apo (<~35.5) and an open holo (>38) indicate a non-leaky, switchable sensor.

## Priority for testing

1. **E106L** — single mutation, **already validated** in your scan (testosterone-selective). Best positive control / quickest win.
2. **des0039, des0044, des0060** (primary) — multi-site designs whose core mutations **I61L + L85I** independently show testosterone-over-progesterone selectivity in your scan, and which pass the structural switch gate.
3. **des0057, des0018, des0007, des0003** (secondary) — additional gate-passing D-ring designs for breadth.

## Design summary

| ID | tier | mutations (model) | mutations (experimental) | apo Å | holo Å | Δ Å |
|---|---|---|---|---|---|---|
| WT_AcrR | reference | — | — | — | — | — |
| E106L | validated single-mut | E106L | E115L |  |  |  |
| des0039 | primary | I61L; L85I; L122F; L143I; L146I; L147F | I70L; L94I; L131F; L152I; L155I; L156F | 33.327 | 42.046 | 8.719 |
| des0044 | primary | I61L; L85I; L122F; L143I; L146I | I70L; L94I; L131F; L152I; L155I | 33.773 | 39.313 | 5.54 |
| des0060 | primary | I61L; L85I; L146I | I70L; L94I; L155I | 34.357 | 38.123 | 3.766 |
| des0057 | secondary | I61L; L122F; L146I | I70L; L131F; L155I | 34.612 | 40.391 | 5.779 |
| des0018 | secondary | I61L; L143I; L146I | I70L; L152I; L155I | 34.249 | 39.454 | 5.205 |
| des0007 | secondary | I61L; L143I; L146I; L147I | I70L; L152I; L155I; L156I | 34.93 | 38.777 | 3.847 |
| des0003 | secondary | L122I; L146I; L147I | L131I; L155I; L156I | 35.364 | 38.522 | 3.158 |

## Expected phenotype

All designs are engineered to **respond to testosterone while suppressing the response to progesterone, cortisol, and estradiol** (estradiol is a non-responder for wild-type AcrR). Wild-type baseline (your assay, GFP fold-induction): testosterone 135, progesterone 60, cortisol 104, estradiol 0.8. Suggested readout: dose-response (GFP) for **all four steroids** to quantify both amplitude and selectivity.

## FASTA sequences (monomer, 182 aa)

```
>WT_AcrR  | wild type
MPGRGGILDAATRLFATHGVSGTSLQQIAGAAGITKAAVYHHFPTKEEVVAAVLAPALEA
IDALVRTAEAHDEPRTRTEAAIIGLADQAVTHRQRWAVLLQDAAVEEYIRNDPGHDELFT
RLRGLLTGPGPDPGTRLQVALFLSGLLGPAQDPSCADIDDDDLRAGIVRAGRLLLLDGAA
TG
>E106L  | mut(model): E106L  | mut(exp): E115L
MPGRGGILDAATRLFATHGVSGTSLQQIAGAAGITKAAVYHHFPTKEEVVAAVLAPALEA
IDALVRTAEAHDEPRTRTEAAIIGLADQAVTHRQRWAVLLQDAAVLEYIRNDPGHDELFT
RLRGLLTGPGPDPGTRLQVALFLSGLLGPAQDPSCADIDDDDLRAGIVRAGRLLLLDGAA
TG
>des0039  | mut(model): I61L; L85I; L122F; L143I; L146I; L147F  | mut(exp): I70L; L94I; L131F; L152I; L155I; L156F
MPGRGGILDAATRLFATHGVSGTSLQQIAGAAGITKAAVYHHFPTKEEVVAAVLAPALEA
LDALVRTAEAHDEPRTRTEAAIIGIADQAVTHRQRWAVLLQDAAVEEYIRNDPGHDELFT
RFRGLLTGPGPDPGTRLQVALFISGIFGPAQDPSCADIDDDDLRAGIVRAGRLLLLDGAA
TG
>des0044  | mut(model): I61L; L85I; L122F; L143I; L146I  | mut(exp): I70L; L94I; L131F; L152I; L155I
MPGRGGILDAATRLFATHGVSGTSLQQIAGAAGITKAAVYHHFPTKEEVVAAVLAPALEA
LDALVRTAEAHDEPRTRTEAAIIGIADQAVTHRQRWAVLLQDAAVEEYIRNDPGHDELFT
RFRGLLTGPGPDPGTRLQVALFISGILGPAQDPSCADIDDDDLRAGIVRAGRLLLLDGAA
TG
>des0060  | mut(model): I61L; L85I; L146I  | mut(exp): I70L; L94I; L155I
MPGRGGILDAATRLFATHGVSGTSLQQIAGAAGITKAAVYHHFPTKEEVVAAVLAPALEA
LDALVRTAEAHDEPRTRTEAAIIGIADQAVTHRQRWAVLLQDAAVEEYIRNDPGHDELFT
RLRGLLTGPGPDPGTRLQVALFLSGILGPAQDPSCADIDDDDLRAGIVRAGRLLLLDGAA
TG
>des0057  | mut(model): I61L; L122F; L146I  | mut(exp): I70L; L131F; L155I
MPGRGGILDAATRLFATHGVSGTSLQQIAGAAGITKAAVYHHFPTKEEVVAAVLAPALEA
LDALVRTAEAHDEPRTRTEAAIIGLADQAVTHRQRWAVLLQDAAVEEYIRNDPGHDELFT
RFRGLLTGPGPDPGTRLQVALFLSGILGPAQDPSCADIDDDDLRAGIVRAGRLLLLDGAA
TG
>des0018  | mut(model): I61L; L143I; L146I  | mut(exp): I70L; L152I; L155I
MPGRGGILDAATRLFATHGVSGTSLQQIAGAAGITKAAVYHHFPTKEEVVAAVLAPALEA
LDALVRTAEAHDEPRTRTEAAIIGLADQAVTHRQRWAVLLQDAAVEEYIRNDPGHDELFT
RLRGLLTGPGPDPGTRLQVALFISGILGPAQDPSCADIDDDDLRAGIVRAGRLLLLDGAA
TG
>des0007  | mut(model): I61L; L143I; L146I; L147I  | mut(exp): I70L; L152I; L155I; L156I
MPGRGGILDAATRLFATHGVSGTSLQQIAGAAGITKAAVYHHFPTKEEVVAAVLAPALEA
LDALVRTAEAHDEPRTRTEAAIIGLADQAVTHRQRWAVLLQDAAVEEYIRNDPGHDELFT
RLRGLLTGPGPDPGTRLQVALFISGIIGPAQDPSCADIDDDDLRAGIVRAGRLLLLDGAA
TG
>des0003  | mut(model): L122I; L146I; L147I  | mut(exp): L131I; L155I; L156I
MPGRGGILDAATRLFATHGVSGTSLQQIAGAAGITKAAVYHHFPTKEEVVAAVLAPALEA
IDALVRTAEAHDEPRTRTEAAIIGLADQAVTHRQRWAVLLQDAAVEEYIRNDPGHDELFT
RIRGLLTGPGPDPGTRLQVALFLSGIIGPAQDPSCADIDDDDLRAGIVRAGRLLLLDGAA
TG
```

## Important caveats (please read)

- These are **computational designs**. Only **E106L** has direct wet-lab support so far; the multi-site designs are predictions and need experimental confirmation.
- The **dG scores cannot reliably resolve ~1 kcal/mol selectivity differences** (testosterone-vs-progesterone is within the method's noise). Leads were therefore chosen by the **structural switch gate + convergence with your empirical scan**, not by the dG margin alone.
- The **gate (DBD opening) is a single-predictor structural proxy** and is sensitive to modeling assumptions; treat predicted amplitude as a hypothesis to be measured, not a guarantee.
- No experimental AcrR–steroid structure exists; binding poses are predicted. **The assay is the arbiter.**
- Avoid over-bulky substitutions at the basal interface (e.g. A57M/A66M caused ~200× basal leak in the scan); the designs here use tolerated changes (I61L, L85I, etc.).


*Companion machine-readable file: `AcrR_testosterone_sensor_designs.csv` (same data + dG columns + full sequences).*
