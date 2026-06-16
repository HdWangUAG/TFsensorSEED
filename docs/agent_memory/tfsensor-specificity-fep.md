---
name: tfsensor-specificity-fep
description: E106L testosterone-specificity FEP (2026-06-16) converged but failed to match assay; root cause = unvalidated Boltz poses + second-shell target; fix recipe
metadata: 
  node_type: memory
  type: project
  originSessionId: a8b6a708-ed73-43fe-b948-ff262bc39f09
---

Stage-3 Tier-2 specificity validation (2026-06-16): ran generalized protein-mutation RBFE for **E106L** (both chains) in all 4 steroid-bound complexes + apo, overnight on 1 GPU (~80 min/leg, 6.5 h). Campaign dir `results/stage3_fep/e106l_specificity/` (run_rbfe_general.sh = env-driven executor; drive_specificity.sh; prep_ligands.py; analyze_specificity.py; SPECIFICITY_RESULTS.md).

**Result: well-converged (±2–3 kJ/mol, BAR≈CGI) but WRONG vs wet-lab.** FEP says E106L favors progesterone (S(prog)=dG_bound(prog)−dG_bound(test)=−14.7 kJ/mol) — opposite of the assay (E106L = clean testosterone switch: cort 104→1.8, prog 60→5.6, test 135→26).

**Why (diagnosed — this is the lesson):**
1. **E106 is SECOND-SHELL** in every Boltz pose (carboxylate→ligand 4.7–6.5 Å); **R123 is the real A-ring anchor** (2.1–3.1 Å). Mutating a second-shell residue gives 1–3 kJ/mol signal = below pose-noise floor.
2. **cortisol complex unstable** — ligand drifted ~11 Å (4.9→15.8 Å from pos106) in 400 ps equil (no ligand restraint) → dG_bound(cort) meaningless.
3. **Poses are unvalidated Boltz predictions** (no crystal; testosterone flipped 3/3 historically); testosterone is the REFERENCE leg so its error propagates into all S(comp). See [[tfsensor-first-principles-recognition]].
4. binding-ΔΔG ≠ fold-induction (assay = binding × allostery; E106L effect is partly allosteric/second-shell).

**Why:** GIGO — the FEP engine is sound (validated, reusable) but specificity at 1–3 kcal/mol needs trustworthy first-shell inputs.

**How to apply (next FEP run):** (a) restrain steroid A-ring to R123 during equil + add per-leg ligand-stability gate (reject >3 Å drift); (b) target a FIRST-shell design (D-ring L85/I61/L146 bump-and-hole, [[tfsensor-dring-campaign]]), not second-shell E106; (c) ≥3 replicates/leg; (d) consider ligand-ligand RBFE for test/prog/cort (clean maps; estradiol excluded). Pipeline + CUDA-GROMACS install notes in [[tfsensor-stage3-pipeline]]. NOTE: ambertools/acpype + CUDA gromacs get dropped/reverted by conda re-solves — reinstall `ambertools` and pin `gromacs=*=nompi_cuda_*` together.
