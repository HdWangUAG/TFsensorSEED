---
name: tfsensor-stage3-pipeline
description: TFsensor Stage-3 automated 4-tier estradiol-biosensor design pipeline (gen→flex-ddG→34Å gate→FEP); built & executing
metadata: 
  node_type: memory
  type: project
  originSessionId: a8b6a708-ed73-43fe-b948-ff262bc39f09
---

TFsensorSEED Stage-3 (2026-06-14): full automated design pipeline built per `LAB_MANUAL.md`/`DEV_STATUS.md`. Driver `drive_stage3.sh [phases]`. Modules in `tfsensor/`:
- **Tier-0 `ligandmpnn_gen.py`** — motif-anchored LigandMPNN on the estradiol-holo scaffold; forces **Arg123→Glu/Asp** (omit_AA_per_residue keeps only D,E), redesigns 28-pos pocket both chains, homodimer symmetry (needs --symmetry_weights). Paths must be ABSOLUTE (run.py cwd=~/my_ligandmpnn). Env ~/LC-Seed/envs/ligandmpnn/.venv; ckpt ligandmpnn_v_32_010_25.pt.
- **Tier-1 `design_score.py`** — flex-ddG specificity screen (sharded parallel, reuses ddg_mutation). **DESIGN target=estradiol** (NOT panel-CSV target=testosterone — must override). margin = dG(estradiol) − min(dG decoys); <0 = specific.
- **Tier-1.5 `design_gate.py`** — absolute 34Å geometric gate: fold matched mutant apo + estradiol-holo (Boltz), require Apo<35.5Å, Holo>38Å, Holo−Apo>0.
- **Tier-2 FEP — NOW INSTALLED & DEMONSTRATED (2026-06-15).** conda env `fep` = GROMACS 2025.4 **CUDA** build (the conda-forge default is OpenCL-only → "no GPU detected" on NVIDIA; must `conda install gromacs=*=nompi_cuda_*`), pmx develop (build from git, py3), acpype/AmberTools, OpenMM. Executor = `results/stage3_fep/proto_l147r_cortisol/run_rbfe.sh <bound|apo>` (pmx hybrid-topology non-eq TI, Crooks/BAR/Jarzynski). Key build gotchas: genion group=**SOL** not CL; cortisol GAFF2 via acpype; **hybrid dummies detonate at dt=2fs → need EM(emtol100)→restrained NVT warm-up(dt=1fs,−DPOSRES)→NPT**; `trjconv -skip` is FRAMES not steps. Demo ddG: dG_bound=−634.8, dG_apo=−626.2 → **ΔΔG_bind(WT→L147R,cortisol) ≈ −9 to −27 kJ/mol (favorable, sign-correct vs "L147R gains cortisol")**; demo-scale (8 transitions×50ps, chain A only) so sign robust but magnitude unconverged. Report: `results/stage3_fep/proto_l147r_cortisol/FEP_DEMO_RESULTS.md`. Production needs both chains A+B, 21λ×5ns (or ≥50 transitions), ≥3 replicates.

**Phase 1+2 results:** 990 sampled → **65 unique designs** (low-temp diversity limited); Top-20 by estradiol margin. Best des0040 (margin −2.00, estr −24.8 vs decoys ≥−22.8), des0030 (−1.89), des0049 (−1.79). Estradiol is top binder in all top designs but margins modest (~1–2 kcal/mol) and **cortisol stays the closest competitor** (carboxylate rewards its polyol — Stage-1e risk confirmed). Phase 3 gate running on Top-20 (1 seed, GPU ~2h); Phase 4 scaffolded.

**How to apply / next:** designs likely need the full **Glu+Arg+His triad + cortisol-exclusion** (D-ring/polar tweak) beyond the single anchor; raise LigandMPNN temps for more diversity; install GROMACS+pmx to run Tier-2 FEP. See [[tfsensor-ddg-calibration]], [[tfsensor-first-principles-recognition]].


## First full-funnel outcome (2026-06-15)
Ran all phases. Funnel: 65 designs → Top-20 (Tier-1, estradiol best binder, leads des0040/des0030/des0049) → **0/20 pass Tier-1.5 gate**. Bottleneck = AGONIST check: estradiol-holo DBD only 35–37 Å (never >38 Å strong-agonist threshold); ~12/20 pass basal (apo<35.5, tight non-leaky) and not-dead (Δ+0.7..1.8). I.e. designs make estradiol BIND + keep tight apo but estradiol fails to OPEN the switch (weak-agonist aromatic A-ring, Stage-1c echo) — binding≠efficacy again. Leads for wet-lab/FEP: des0007 (apo 33.78,Δ+1.79), des0040. Gate path fix: Boltz output dir is boltz_results_<inputs_basename> (=design id), not boltz_results_inputs. NEXT: design AGAINST Holo−Apo (activation), full Glu+Arg+His triad + cortisol-exclusion, higher MPNN temp for diversity. Report: results/stage3_design/STAGE3_SUMMARY.md.