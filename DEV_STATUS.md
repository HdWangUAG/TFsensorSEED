# TFsensorSEED Development Status

**Date Updated:** June 16, 2026
**Current Phase:** Stage 3 multi-ligand specificity campaigns + Tier-2 FEP, running across nodes.
**Live state & job allocation:** `PROGRESS.md` + `JOBS_REGISTRY.csv` (single source of truth). Cross-server setup: `HANDOFF.md`. Sections 1–5 below are historical (Jun 14–15); **§6 = current.**

## 1. Today's Major Milestones & Discoveries

*   **Identified DL Model Limitations:** Benchmarking (`Stage 1d`) revealed that Deep Learning models (Boltz-2/Protenix) generate excellent static structures but are completely blind to the $\Delta\Delta G$ shifts of single-point mutations. Their pose prediction noise swamps the microscopic binding signals.
*   **Established PyRosetta Tier-1 Filter:** Successfully built and validated a `flex-ddG` style PyRosetta pipeline (`ddg_panel.py`). By introducing **local backbone flexibility** and **ligand tethering**, we eliminated false-negative clashes. The engine successfully replicated the experimental L147R specificity inversion (scoring Cortisol > Testosterone).
*   **Decoded the "34 Å" Allosteric Gating Rule:** Apo/Holo analysis (`two_state_panel.py`) proved that DL models cannot quantitatively predict fluorescence amplitude. However, we discovered a vital absolute geometric rule:
    *   Tight DNA binders (WT, F119W) have an Apo state strictly matching the DNA major groove spacing (**~34.0 Å**).
    *   Leaky mutants (L147R, ~10% basal leak) physically bulge in the Apo state to **> 36.0 Å**, operating at hyper-sensitive concentrations (1-5 µM) because they weakly bind DNA.
    *   This discovery converts the flawed amplitude predictor into a powerful **Binary Gating Filter (Tier 1.5)** to eliminate dead-binders and constitutively leaky designs.

## 2. Updated Pipeline Architecture (Stage 3)

The overarching engineering strategy has shifted from "Blind Sampling" to "Hypothesis-Driven Target Grafting". The automated pipeline (pending Claude's execution) is structured as follows:

*   **Tier 0 (Generation):** Constrained LigandMPNN. Hardcode the Estrogen Anchor (`Arg123Glu/Asp`) to satisfy the estradiol 3-OH phenol constraint, and allow MPNN to repack the 1st/2nd shell.
*   **Tier 1 (Affinity):** PyRosetta `flex-ddG`. Screen 10,000+ sequences. Extract Top ~20 with supreme relative specificity for Estradiol.
*   **Tier 1.5 (Gating):** Boltz-2 Two-State Filter. Enforce Mutant Apo ≤ 35.5 Å (no leakiness) and Mutant Holo > 38.0 Å (strong agonist).
*   **Tier 2 (Arbiter):** Free Energy Perturbation (FEP). Calculate absolute RBFE for the surviving elite sequences before ordering gene synthesis.

## 3. Current Action Items
*   Claude (CLI Agent) has received the master `/goal` prompt.
*   Awaiting Claude to scaffold the `drive_stage3.sh` overarching bash script.
*   Awaiting Claude to set up the FEP prototype pipeline for testing the dual-topology generation against a known ground truth (e.g., WT vs L147R Cortisol).

---
## 4. Stage-3 Pipeline — BUILT & EXECUTING (Claude, June 14 2026)

The full 4-phase automation is implemented, smoke-validated end-to-end, and Phases 1–2 are running.

**Modules (in `tfsensor/`):**
- `ligandmpnn_gen.py` — Tier-0 motif-anchored LigandMPNN. Forces Arg123→Glu/Asp via `omit_AA_per_residue`, redesigns the 28-position pocket (both chains), homodimer symmetry. Smoke: 100% of designs carry the anchor.
- `design_score.py` — Tier-1 flex-ddG specificity screen (sharded, parallel). **Target = estradiol** (engineering goal, not the panel-CSV WT-validation target). Ranks by `margin = dG(estradiol) − min(dG decoys)`; <0 = estradiol-specific.
- `design_gate.py` — Tier-1.5 absolute-geometry gate (34 Å rule): folds matched mutant apo + estradiol-holo (Boltz), enforces Apo<35.5 Å, Holo>38 Å, Holo−Apo>0.
- `fep_rbfe.py` — Tier-2 RBFE scaffold. Prepares the WT↔L147R/cortisol prototype thermodynamic cycle + endpoints; detects engines; **FEP execution gated on installing GROMACS+pmx** (none present) — see `results/stage3_fep/.../SETUP_FEP.md`.
- `drive_stage3.sh` — links all phases (`./drive_stage3.sh [phases]`).

**Status:** Phase 1 (1000 seqs) + Phase 2 (screen → Top 20) executing. Phase 3 (GPU gate) runs after the screen. Phase 4 scaffolded + prototype prepared (execution deferred on tool install).

**Smoke finding:** best single-anchor designs reach only modest estradiol margins and cortisol stays competitive (carboxylate also rewards cortisol's polyol — consistent with Stage-1e). → designs likely need the full Glu+Arg+His triad + a cortisol-exclusion tweak; Tier-1.5/Tier-2 will filter.

## 5. June 15 Updates (D-Ring Specificity & Leaky Mutants)

*   **First Stage-3 Run Finished (Estradiol target):** 65 unique designs generated. PyRosetta `flex-ddG` successfully found 20 designs highly specific to Estradiol (Phase 2 passed). However, ALL 20 designs failed the Boltz-2 Apo/Holo gate (Phase 3). They bound the ligand but failed to open the DBD > 38 Å (dead-binders). This confirms binding $\neq$ activation.
*   **D-Ring Steric Strategy Initiated (`drive_dring.sh`):** To specifically distinguish Testosterone from Progesterone, we initiated a new pipeline fixing Arg123/Glu106 (A-ring anchors) while introducing bulky mutations at the D-ring to sterically clash with Progesterone's bulky 20-acetyl group. Phase 1 generated the library; Phase 2 is currently running.
*   **Validating the Apo Gate (Catastrophic Leaky Mutants):** Experimental data confirmed that introducing too much bulk inappropriately (e.g., A66M / model A57M) causes a 200x spike in basal fluorescence (catastrophic leaky). The bulky Methionine completely prevents the Apo state from closing. Tolerable mutations like A66L and I70L (model I61L) maintain function. Our Tier-1.5 Boltz Apo Gate (< 35.5 Å) is perfectly positioned to predict and filter out these true negative (catastrophic leaky) candidates.

---
## 6. June 16 Update — Tier-2 FEP built, multi-ligand campaigns, cross-server

**Tier-2 FEP is now BUILT, INSTALLED, and VALIDATED** (was scaffold-only before).
- Engine: **pmx hybrid-topology + GROMACS (CUDA) non-equilibrium TI** (Crooks/BAR/Jarzynski), GPU. Env recipe + gotchas in `HANDOFF.md §2` (CUDA-pin GROMACS — conda default is OpenCL; ambertools+gromacs together; pmx from git, not pip; genion=SOL; hybrid dt-warmup ladder).
- **Demo (L147R × cortisol):** closed the thermodynamic cycle, ΔΔG_bind = −8.6 kJ/mol (BAR), **sign-correct** vs assay. `results/stage3_fep/proto_l147r_cortisol/FEP_DEMO_RESULTS.md` + `FEP_demo_figure.png`.
- **E106L specificity FEP (4 ligands + apo):** well-converged (±2–3 kJ/mol) but **fails to reproduce the assay** — diagnosed as GIGO (E106 is **second-shell** to the ligand; the cortisol complex was unstable; poses are unvalidated). Lesson: a meaningful specificity FEP needs a **restrained/validated pose + a first-shell target**. `results/stage3_fep/e106l_specificity/SPECIFICITY_RESULTS.md`.
- Reusable executors live in **`scripts/fep/`** (`run_rbfe_general.sh`, `prep_ligands.py`, `analyze_specificity.py`, …).

**Tier-1.5 gate — major caveat found.** The original D-ring gate (7/12 pass) folded **1 ligand on the homodimer**. At the biologically-correct **2 ligands** the holo opens much wider (~44 Å), and **Protenix disagrees with Boltz** on opening. → the "agonist pass" is single-predictor + wrong-stoichiometry-sensitive. **Re-running the 2-ligand gate on all 71 D-ring designs** (`results/stage3_dring/gate2lig/`, `scripts/gate/drive_gate2lig.sh`). **Amplitude is now treated as a wet-lab readout**, not a trusted filter. The trusted specificity signal is the empirical scan (I61L/L85I/E106L) + design convergence.

**Multi-ligand specificity campaigns (recognition-code, hypothesis-driven):**
- **Testosterone** (done): leads **des0039 / des0044 / des0060** (I61L+L85I core) + single **E106L** (wet-lab validated). Deliverable for the bench: `deliverables/AcrR_testosterone_sensor_designs.{md,csv}` (FASTA + mutations in model & experimental numbering + caveats).
- **Progesterone**: ligand-aware D-ring + mild S/T/N/Q (C20 acetyl) bias, keep A-ring.
- **Cortisol**: **R123E anchor** (wet-lab-validated cortisol switch) + polar D-ring (S/T/N/Q).
- **Estradiol**: Glu/Arg/His phenol clamp (prior single-anchor run failed the gate).

**Engineering / infra.**
- Refactored tool paths into `tfsensor/config.py` + `.env` (`.env.example` provided); `design_score.py` uses `ThreadPoolExecutor`; robust LigandMPNN FASTA parsing; 2-ligand gate support in `design_gate.py`.
- **GitHub:** pushed to `https://github.com/HdWangUAG/TFsensorSEED` (code + docs + agent-memory mirror in `docs/agent_memory/` + `data/`).
- **Node-Aspartate** (`129.215.109.43`, 2nd GPU): received `data/` + WT-validation poses (rsync, 202 MB). **prog/cort/estradiol generation + flex-ddG screen reassigned to Aspartate** (the Alpha queue was cancelled). Alpha keeps the 2-ligand gate + FEP/RBFE. See `JOBS_REGISTRY.csv`.

**Next:** finish 2-ligand gate (Alpha) → compare vs 1-ligand; run prog/cort/estradiol gen+screen (Aspartate); build the **ligand-ligand RBFE (ΔΔΔG) executor** for the test/prog/cort triad (Beta) — the rigorous specificity tool that avoids the E106L second-shell pitfall.
