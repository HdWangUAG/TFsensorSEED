# Memory Index

- [TFsensor Stage-1](tfsensor-stage1-triple-nogo.md) — WT responds to testosterone not estradiol; binding-only fails, the bind×switch coupled method validates (estradiol = dark non-responder)
- [TFsensor mutant benchmark](tfsensor-mutant-benchmark.md) — Stage-1d: fast DL+single-pose pipeline fails F119W/L147R recap (1/9); DL mutation-blind; need fixed-backbone ΔΔG/FEP; hold Stage-3
- [TFsensor first-principles recognition](tfsensor-first-principles-recognition.md) — Stage-1e: PDB-mined recognition code; estradiol=Glu/Arg phenol clamp; explains WT/mutants; data-driven estradiol design recipe
- [PyRosetta init once per process](tfsensor-pyrosetta-init-once-per-process.md) — loop ligand dG via subprocess; absolute work dirs; use_distance_cst is now a getter
- [TFsensor ΔΔG calibration](tfsensor-ddg-calibration.md) — Stage-3a fixed-backbone ΔΔG attempt-1 failed 0/10 (clashing baselines); fix = pre-relax + backrub ensemble
- [TFsensor Stage-3 pipeline](tfsensor-stage3-pipeline.md) — automated 4-tier design (gen→flex-ddG→34Å gate→FEP); 65 designs, top des0040; FEP needs GROMACS+pmx install
- [TFsensor numbering convention](tfsensor-numbering-convention.md) — use MODEL/design index everywhere (F128W=F119W, L156R=L147R, +9); never experimental
- [TFsensor D-ring campaign](tfsensor-dring-campaign.md) — testosterone>progesterone via C17 bump-and-hole; design {61,85,122,143,146,147}, keep Arg123/Glu106; rank dG(test)-dG(prog)
- [TFsensor empirical scan](tfsensor-empirical-scan.md) — 85-mutant GFP data: R123E→cortisol (validates ΔΔG), estradiol unreachable by point-mut, E106L/L85I/I61L=testosterone-specific
- [TFsensor specificity FEP](tfsensor-specificity-fep.md) — E106L overnight RBFE converged but failed vs assay; GIGO from second-shell target + unstable/unvalidated Boltz poses; fix = restrain pose+first-shell target+replicates
- [TFsensor node aspartate](tfsensor-node-aspartate.md) — 2nd GPU node bring-up (2026-06-16): real env paths (/opt/LigandMPNN, ~/.conda envs), flex-ddG+gen ready; blockers = nvidia driver mismatch, broken boltz2 env, no synced results
