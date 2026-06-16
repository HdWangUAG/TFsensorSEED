---
name: tfsensor-mutant-benchmark
description: TFsensor Stage-1d — fast DL+single-pose pipeline fails to recapitulate F119W/L147R mutant phenotypes (1/9); DL is mutation-blind
metadata: 
  node_type: memory
  type: project
  originSessionId: a8b6a708-ed73-43fe-b948-ff262bc39f09
---

TFsensorSEED Stage-1d benchmarked the pipeline against real mutant data (2026-06-14). **Numbering: experimental construct is +9 vs our model — F119W = our F119W, L147R = our L147R** (both pocket residues; mapping unique & verified; in `data/mutants.json`). Built mutant inputs via `--mutate` (boltz_holo_inputs, protenix_runner), ran Boltz+Protenix (same settings as WT), then physics_panel/trigger_panel/biosensor_score with new `--prefix`. Cross-variant comparator: `tfsensor/benchmark_compare.py`. Drivers: `drive_mutants.sh`, `drive_mutants_analysis.sh`. Results in `results/stage1d_mutants/` (BENCHMARK_REPORT.txt, BENCHMARK_INTERPRETATION.md).

**Result: 1/9 experimental expectations recapitulated — the fast pipeline does NOT predict the mutant biochemistry.** Causes (separable): (1) **Boltz/Protenix are mutation-blind** for single pocket point mutations — Protenix ligand-ipTM flat to 3 dp across all variants/ligands, Boltz binder-prob moves only at noise (mutations ARE in the predicted structures: f119w pose=TRP@119, l147r=ARG@147 — readout is insensitive). (2) **Single-pose Rosetta dG on independently re-predicted backbones is confounded** — L147R makes every complex relax worse (cortisol the worst, backwards vs experiment where cortisol is preferred); need fixed-backbone ΔΔG instead. (3) **Trigger axis used WT crystal apo for mutant holo** — need matched per-mutant apo; L147R opening went UP (should attenuate). Underlying: phenotypes are EC50/dynamic-range (F119W ~3-log ≈ ~4 kcal/mol; L147R inversion) — thermodynamic-cycle quantities single static poses can't resolve.

**How to apply:** demote Boltz/Protenix confidence as a mutation/affinity ranker (keep for pose gen + WT responder/non-responder split which worked, see [[tfsensor-stage1-triple-nogo]]); promote **fixed-backbone ΔΔG_binding** (Rosetta cartesian_ddg / flex-ddG, thread mutation onto WT holo complex) and **FEP** for EC50-scale calls; predict mutant apo for the trigger axis. **HOLD Stage-3 generation until ≥1 physics instrument reproduces a known mutant phenotype** (calibrated filter is prerequisite). See [[tfsensor-pyrosetta-init-once-per-process]].
