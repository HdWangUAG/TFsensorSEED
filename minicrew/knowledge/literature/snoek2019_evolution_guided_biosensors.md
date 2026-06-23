---
title: Evolution-guided engineering of small-molecule biosensors
authors: Snoek et al.
year: 2019
doi: 10.1093/nar/gkz954
tags: [AcrR, steroid-recognition, allostery]
relevance: method
trust: HIGH
---

## Claim / finding (1–3 bullets, with the numbers)
- A high-throughput method evolves prokaryotic allosteric transcription factor (aTF) specificity and transfer functions in *S. cerevisiae*; a single round of effector-binding-domain (EBD) mutagenesis + toggled selection yields BenM (cis,cis-muconic acid sensor) variants with changed ligand specificity, increased dynamic output range, shifted operational range, and inversion-of-function (activation→repression). 〔src: "From a single round of mutagenesis of the effector-binding domain (EBD) coupled with various toggled selection regimes, we robustly select aTF variants of the cis,cis-muconic acid-inducible transcription factor BenM evolved for change in ligand specificity, increased dynamic output range, shifts in operational range, and a complete inversion-of-function from activation to repression."〕
- Targeting only the EBD preserved DNA-binding affinity similar to wild-type BenM, and evolved biosensors remained functional when ported back into a prokaryotic chassis. 〔src: "by targeting only the EBD, the evolved biosensors display DNA-binding affinities similar to BenM, and are functional when ported back into a prokaryotic chassis."〕
- No specific quantitative effect sizes (fold-changes, EC50, KD) are reported in the abstract. TODO

## Key data (tables / SI)
- TODO (abstract-only source; no tables or SI available)

## SI / supplementary notes
- TODO (abstract-only source; no SI available)

## Why it matters to TFsensor
- Demonstrates that mutagenizing only the effector-binding domain (analogous to the AcrR ligand pocket) can retune ligand specificity and transfer-function shape while preserving DNA binding/allosteric coupling — directly relevant to designing AcrR pocket variants for steroid recognition without breaking allostery. 〔src: "by targeting only the EBD, the evolved biosensors display DNA-binding affinities similar to BenM"〕
- Validates a portable engineering strategy (evolve in yeast, deploy in prokaryote) and the four tunable axes we care about: specificity, dynamic range, operational range, and activation/repression sign. 〔src: "evolved for change in ligand specificity, increased dynamic output range, shifts in operational range, and a complete inversion-of-function from activation to repression."〕

## Applicability caveats
- System is the LysR-type TF BenM (cis,cis-muconic acid ligand), not AcrR/steroids; transfer of pocket-engineering principles to steroid recognition is by analogy only. 〔src: "we robustly select aTF variants of the cis,cis-muconic acid-inducible transcription factor BenM"〕
- Method developed in a eukaryotic (yeast) chassis with prokaryote back-porting; assay/chassis differences may affect AcrR behavior. 〔src: "a versatile and high-throughput method to evolve prokaryotic aTF specificity and transfer functions in a eukaryote chassis, namely baker's yeast Saccharomyces cerevisiae."〕
- Abstract-only note: no numeric effect sizes, mutant panels, or dose-response data were available to verify. TODO (mine full text + SI before relying on quantitative claims)