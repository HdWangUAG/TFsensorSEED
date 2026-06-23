---
title: Engineering an allosteric transcription factor to respond to new ligands
authors: N. Taylor et al.
year: 2015
doi: 10.1038/nmeth.3696
tags: [AcrR, steroid-recognition, allostery]
relevance: method
trust: HIGH
---

## Claim / finding (1–3 bullets, with the numbers)
- Engineered the *E. coli* lac repressor (LacI) — a bacterial allosteric transcription factor (aTF) — to respond to one of four new inducers: fucose, gentiobiose, lactitol, or sucralose; variants were "comparable in specificity and induction to wild-type LacI with its inducer, isopropyl β-D-1-thiogalactopyranoside (IPTG)" 〔src: "we identified new variants comparable in specificity and induction to wild-type LacI with its inducer, isopropyl β-D-1-thiogalactopyranoside (IPTG)."〕 (no numeric effect sizes in abstract — TODO)
- Methods combined computational protein design, single-residue saturation mutagenesis or random mutagenesis, with multiplex assembly 〔src: "Using computational protein design, single-residue saturation mutagenesis or random mutagenesis, along with multiplex assembly, we identified new variants…"〕
- Central challenge framed: altering inducer specificity is hard because "substitutions that affect inducer binding may also disrupt allostery" 〔src: "Altering inducer specificity in these proteins is difficult because substitutions that affect inducer binding may also disrupt allostery."〕

## Key data (tables / SI)
- TODO (abstract-level source only; no tables or SI available)

## SI / supplementary notes
- TODO (no SI provided)

## Why it matters to TFsensor
- Demonstrates a generalizable strategy — computational design + saturation/random mutagenesis + multiplex screening — for re-specifying an aTF's effector while preserving allostery; directly analogous to redesigning AcrR's ligand pocket to recognize steroids without breaking allosteric induction.
- Explicitly identifies the core design tension (binding-altering substitutions can break allostery) that any AcrR steroid-biosensor pocket redesign must navigate.

## Applicability caveats
- System is LacI (a LacI/GalR-family sugar-responsive repressor), not AcrR (TetR family); fold, allosteric mechanism, and natural ligands (sugars vs. lipophilic steroids) differ substantially.
- New inducers are sugar derivatives (fucose, gentiobiose, lactitol, sucralose), not steroids — pocket chemistry and hydrophobicity transfer is uncertain.
- Abstract-only: no quantitative EC50/KD, fold-induction, or mutant-panel data extracted; numeric transferability cannot be assessed from this source.