---
title: Computational tool capabilities & resolution limits
trust: MEDIUM
tags: [flex-ddG, boltz, fep, ligandmpnn, scoring]
---

What each tool in the funnel can and cannot tell us (so agents don't over-trust
a number):

- **LigandMPNN (Tier-0)** — sequence generation conditioned on the ligand. Good
  for proposing diversity; says nothing about ΔΔG or selectivity.
- **Rosetta flex-ddG (Tier-1, CPU)** — relative ΔΔG ranker. Resolution ~1
  kcal/mol at best; margins near the noise floor are NOT rank-able. Tethered
  ligand prevents ejection (decoys can be kept in productive poses); backrub +
  local min optimise the given pose only. REU ≠ kcal/mol; explicit waters and
  long-range electrostatics weak. Report per-seed spread / CI, not a point value.
- **Boltz-2 (Tier-1.5 gate, GPU)** — apo/holo structure prediction. Used as a
  DBD-opening gate (distance spacing). Blind to single-mutation ΔΔG; pose noise
  can swamp the signal; "high-confidence" ≠ validated selectivity. The distance
  thresholds must be validated against known phenotypes before being trusted.
- **FEP / RBFE (Tier-2)** — can arbitrate small margins ONLY if alchemical maps
  are chemically sane and poses/protonation/ordered-waters are fixed. Estradiol
  vs cortisol/progesterone/testosterone are not trivial matched perturbations.

Rule of thumb for any computed number entering a decision: state the method, the
uncertainty, and whether the margin is above the method's resolution.
