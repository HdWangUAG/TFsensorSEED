# TFsensorSEED design pipeline (two-tier, affinity/specificity scope)

Computational scope = **affinity / specificity only**. Allosteric **amplitude**
(dynamic range, dead-binder) is a qualitative check (DBD opens / doesn't crash) and is
ultimately a **wet-lab** readout. Rationale and failures behind these choices:
`results/stage1d_mutants/BENCHMARK_INTERPRETATION.md`, `results/stage3_ddg/BENCHMARK.txt`.

## Tier 0 — hypothesis-driven design (not blind generation)
First-principles PDB recognition code (`results/stage1e_pdbmine/`): estradiol's aromatic
3-OH **phenol** needs a **Glu/Asp carboxylate clamp (+ Arg, + His on 17-OH)**; the
4-en-3-one decoys present a 3-**keto** read by Arg123. Design = graft that estrogen triad
into the AcrR pocket (+ guard against cortisol's polyol hijacking the carboxylate).
LigandMPNN may diversify, but candidates are motif-anchored, not blind.

## Tier 1 — locally-flexible PyRosetta ΔΔG  (cheap; ~10,000 → Top ~10)
`tfsensor/ddg_mutation.py` + `ddg_panel.py` + `ddg_report.py` (`drive_ddg.sh`).
- Pre-relax WT holo complex → clean reference (validated: clean −19..−27 baselines).
- Per backbone seed, backrub-style ensemble; WT & mutant **paired** on each member with
  **local backbone flexibility** (8 Å shell incl. site ±2) so small→large mutations are
  not falsely penalized; ligand **tethered** (anti-ejection). ΔΔG = median over ensemble,
  reported as median across 3 seeds with sign-agreement (robust).
- Rank designs by **relative specificity** (target ligand = lowest ΔΔG of the panel).
- Calibration status: reproduces the L147R specificity-switch direction (testosterone
  penalized; cortisol becomes most-favored) and the carboxylate→keto(progesterone)
  repulsion. Does NOT capture F119W (a sensitivity/EC50 effect → wet-lab, out of scope).
  Use as a RELATIVE ranker, not an absolute-affinity predictor.

## Tier 1.5 — Boltz two-state geometry gate (apo<35.5 Å, holo>38 Å, Δ>0)
- **Caveat (2026-06-16):** the gate is a **single-predictor structural proxy**. Must fold the
  **2 ligands** of the homodimer (one per protomer) — the 1-ligand fold under-opens; at 2 ligands
  holo opens much wider (~44 Å). **Boltz and Protenix disagree** on opening. → use the gate to
  drop clearly-dead/leaky designs, but **treat allosteric amplitude as a WET-LAB readout**, not truth.

## Tier 2 — rigorous arbiter:  FEP
- **STATUS (2026-06-16): BUILT & VALIDATED.** Engine = **pmx hybrid-topology + GROMACS (CUDA)
  non-equilibrium TI** (Crooks/BAR/Jarzynski), not drMD. Executors in `scripts/fep/`; env in `HANDOFF.md §2`.
- Validated on L147R×cortisol (ΔΔG_bind sign-correct vs assay; `FEP_DEMO_RESULTS.md`).
- **Lesson (E106L, `SPECIFICITY_RESULTS.md`):** protein-mutation FEP on *predicted, unrestrained,
  second-shell* inputs is GIGO at ~1 kcal/mol. A trustworthy run needs a **restrained/validated pose +
  first-shell target + replicates**.
- **Preferred specificity tool:** **ligand-ligand RBFE** within {testosterone, progesterone, cortisol}
  (identical A-ring → C17 perturbation maps cleanly; estradiol excluded). ΔΔΔG = how a design shifts
  ΔΔG(target vs rival) vs WT. (Executor: to build.)

## Final selection
Pass Tier-1 relative specificity → Tier-2 FEP confirms estradiol > decoys → wet-lab tests
binding AND amplitude (the part computation hands off).
