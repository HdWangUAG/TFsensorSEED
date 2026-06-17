# TFsensorSEED — progress ledger

Single source of truth for campaign state across nodes. Each node updates its section;
merge = text merge. See `HANDOFF.md` for env/sync/merge mechanics, `docs/agent_memory/`
for the agent's accumulated reasoning. **Numbering = MODEL index everywhere (exp = model + 9).**

_Last updated: 2026-06-16 (Node-aspartate bring-up)_

## Node aspartate (2nd GPU node) — bring-up record, 2026-06-16
New server joined the campaign. Quadro RTX 6000/8000, 36-core. Env layout DIFFERS from the
HANDOFF recipe (no `~/LC-Seed/envs`, no `~/my_ligandmpnn`); tools live in `/opt` + `~/.conda/envs`.
- **Done:** wrote node-local `.env` (paths verified, `config.py` resolves all 5); CPU smoke
  passed — PyRosetta import, `design_score` flex-ddG CLI, `ligandmpnn_gen` import,
  LigandMPNN `run.py` all OK. So **Tier-0 gen (CPU parts) + Tier-1 flex-ddG screen are ready here.**
- **Fixed `boltz2` env (2026-06-16):** was half-provisioned + leaking into a broken `~/.local`.
  Made self-contained (`pip install boltz==2.2.0`, torch **2.7.1+cu126**, lightning, rdkit,
  numba), purged a corrupted dual numpy → 1.26.4, patched `bin/boltz` shebang to `-s` (ignore
  user-site) so it works at every driver call site. `boltz --help` ✅, `pip check` clean.
- **GPU LIVE + boltz2 GPU-verified (2026-06-16, later):** `nvidia-smi` now healthy —
  **Quadro RTX 8000, 48 GB, Driver 580.159.03 / CUDA 13.0** (the driver/library mismatch is
  GONE; no reboot needed in the end). `boltz2` torch reports `cuda_available True`, device
  Quadro RTX 8000, capability (7.5) Turing. **Tier-1.5 Boltz gate is now fully runnable on GPU here.**
  Blocker #1 CLEARED. `.env` boltz warning updated to match.
- **Plan (set 2026-06-16):** testosterone done on Alpha → aspartate samples **prog/cort/estradiol**
  sequence libraries (CPU), then ships sequences to the FEP node for ligand-RBFE.
- **LigandMPNN-on-CPU validated (2026-06-16):** `cuda_available False` → clean CPU fallback (no
  driver crash); `data/AcrR_STR_001.pdb` STR (testosterone) holo scaffold; 10 seqs in 4.2 s,
  300 seqs → 224 unique designs in seconds, 1.1 GB RAM. **Full 1200-seq library = minutes on CPU.**
  So Tier-0 generation is fully runnable here once the right scaffolds are present.
- **HARD DEPENDENCY for the real prog/cort/estradiol libraries:** generation conditions on the
  ligand, and `drive_prog_cort.sh` uses each ligand's WT holo Boltz pose as the `--scaffold`
  (`results/stage1_wt_validation/boltz/seed1/boltz_results_inputs/predictions/wt_<ligand>/wt_<ligand>_model_0.pdb`).
  We only have the testosterone STR holo locally; **need `wt_progesterone/wt_cortisol/wt_estradiol_model_0.pdb`
  rsync'd from Alpha** (gitignored, GPU-made). Same sync also unblocks the flex-ddG screen
  (`_build_complex` reuses each ligand's pre-posed coords; it does NOT dock SMILES de novo).
- **Blocker status — ALL CLEAR (2026-06-16):** (1) GPU driver — ✅ CLEARED (see GPU-LIVE note above).
  (2) WT scaffolds — ✅ CLEARED: Alpha pushed `results/stage1_wt_validation/` (202 MB) via rsync.
  All four seed1 WT holo poses verified intact (test/prog/cort/estradiol, 2688 protein ATOM + chain-L
  ligand HETATM each; HETATM counts scale by steroid size — cortisol 26 > prog 23 > test 21 > estr 20).
  seed42/2024 Boltz replicates + Protenix outputs also synced. **Tier-0/1/1.5 are all runnable here now.**
- **2-ligand WT holo refold (2026-06-16, this node's first GPU compute):** owner flagged that the
  synced WT scaffolds folded only ONE steroid into the AcrR homodimer (chains A,B + 1 ligand L) —
  an unphysical asymmetry. Re-folded **all four** (test/prog/cort/estradiol) with a steroid per
  protomer (ligands L+M) via `boltz_holo_inputs` (default chains A,B already emits 2 ligand blocks;
  affinity head auto-dropped — Boltz can't score 2 copies). Cached MSA wired into the YAMLs (no MSA
  server dep). Outputs in `results/wt_holo_2lig/` (aspartate-owned; mirrors Alpha's path template so
  `--boltz_root`/`_top_boltz_pose` resolve unchanged). **All four high-confidence** (conf 0.91–0.92,
  ligand_iptm 0.95–0.96); both pockets filled, ligands ~19–20 Å apart. flex-ddG made 2-ligand-safe
  (`physics_score._extract_ligand_block` now keeps only the first ligand chain — backward-compatible).
  A/B verified gen is behavior-equivalent old-vs-new (richer ligand context: num_ligand_res 7→14).
- **Prog/cort campaign on aspartate (2026-06-16):** `drive_prog_cort.sh` repointed to the 2-ligand
  scaffolds, Alpha-gate wait removed (own GPU). Gen worked (prog **5**, cort **10** unique designs —
  thin, as expected from the as-spec params; A/B-confirmed it's the spec not the refold).
- **flex-ddG env gap FOUND + FIXED (2026-06-16):** first real screen run scored 0 — every worker
  died at `from lcseed import config` (no `lcseed` pkg on aspartate) and `molfile_to_params.py` was
  absent. The "Tier-1 ready here" bring-up claim was wrong (smoke only tested imports, not the
  scoring path). FIX (portable, helps all nodes): decoupled `physics_score._molfile_to_params` from
  lcseed → resolves pyrosetta python via `tfsensor.config.PYROSETTA_PY`; added `MOLFILE_TO_PARAMS`
  config knob; copied `molfile_to_params.py` + its `rosetta_py` dep node-local to `~/rosetta_tools/`
  (py3-OK, from a Rosetta 2020.08 bundle), wired `TFSENSOR_MOLFILE_TO_PARAMS` into `.env`. Validated
  one worker end-to-end (prog des0000 dG=-23.25 vs WT -22.50). **Re-screen DONE** (prog 5/5, cort
  10/10 scored): prog-selective **des0002 (I61L+Q88T, margin −1.39)**; cort-selective **des0007
  (I61L+Q88T+R123E, margin −1.73)** — all cort leads carry the R123E anchor (matches recognition
  code). Margins ~1 kcal = near the noise floor (see Established conclusions), so treat as a coarse
  ranker → next tier is the 2-ligand Boltz gate + ligand-RBFE, NOT the margin alone.


## Established conclusions (trust these)
- **WT is a 4-en-3-one sensor**: testosterone > cortisol > progesterone; **estradiol = non-responder**.
- **Recognition code** (`results/stage1e_pdbmine/`): A-ring 3-keto ↔ R123/E106/D116 cluster; D-ring/C17 = the selectivity lever among test/prog/cort; estradiol phenol needs a Glu/Arg clamp.
- **DL pose caveat**: no crystal exists; Boltz/Protenix poses are unreliable for orientation/amplitude (testosterone flips). Trust SAR + ΔΔG/FEP for specificity; treat allosteric opening as a **wet-lab** readout.
- **Specificity ≠ resolvable by binding-ΔΔG at ~1 kcal/mol** on predicted poses (3-seed re-score noise; E106L FEP GIGO). Use it as a coarse ranker; the trusted specificity signal is the **empirical scan**.
- **Empirical leads** (`results/stage1f_empirical/`): testosterone-selective = **E106L, L85I, I61L**; **R123E → cortisol** (validated); estradiol unreachable by point mutation.

## Pipeline (4-tier)
Tier-0 LigandMPNN gen → Tier-1 flex-ddG specificity screen → Tier-1.5 Boltz 2-state gate (now **2-ligand**) → Tier-2 FEP/ligand-RBFE. Drivers: `drive_stage3.sh`, `drive_dring.sh`, `drive_prog_cort.sh`. Code refactor: paths via `tfsensor/config.py` + `.env`.

## Campaign status

| Campaign | Stage | State | Key output | Leads / finding |
|---|---|---|---|---|
| Estradiol | full | done | `results/stage3_design/STAGE3_SUMMARY.md` | 65 designs; **0/20 pass gate** (bind ≠ activate) |
| **Testosterone** (D-ring) | gen+screen+gate+validate | done | `results/stage3_dring/validate/VALIDATE_SUMMARY.md` | **des0039, des0044, des0060** (I61L+L85I core); gate 7/12 (1-ligand) |
| Testosterone 2-ligand gate | gate (all 71) | **running** (Alpha) | `results/stage3_dring/gate2lig/gate2lig.json` | re-running gate unbiased + homodimer-correct (1-lig gate was Boltz-specific, Protenix disagreed) |
| FEP demo (L147R×cortisol) | Tier-2 | done | `results/stage3_fep/proto_l147r_cortisol/FEP_DEMO_RESULTS.md` + `FEP_demo_figure.png` | ΔΔG_bind −8.6 kJ/mol (BAR), sign-correct; pipeline validated |
| E106L specificity FEP | Tier-2 | done | `results/stage3_fep/e106l_specificity/SPECIFICITY_RESULTS.md` | converged but **fails vs assay** — GIGO (E106 second-shell, unstable pose). Lesson: restrain pose + first-shell target |
| **Progesterone** | gen+screen+gate | **done** (aspartate, 2-lig) | `results/stage3_prog/GATE2LIG_SUMMARY.md` | 5 designs; **gate 3/3 pass**. Lead **des0002 (I61L+Q88T)** = selective (−1.39) + gates clean; des0000 backup |
| **Cortisol** | gen+screen+gate | **done** (aspartate, 2-lig) | `results/stage3_prog/GATE2LIG_SUMMARY.md` | 10 designs; **gate 1/5 pass** — top-specificity leads (des0007/8/2, all R123E) predicted **leaky** (apo>35.5). Only **des0001 (I61V+Q88L+R123E)** is selective+clean |

## Wet-lab panel (current best, build-and-test)
Testosterone: **des0039 / des0060 / des0044** (I61L+L85I) + single **E106L**. Cortisol: **R123E** (validated) + **des0001 (I61V+Q88L+R123E)** (gate-clean + selective; des0007 higher-specificity but predicted leaky). Progesterone: **des0002 (I61L+Q88T)** (gate-clean + selective) + des0000 backup. Judge by gate + FEP + wet-lab, NOT the ΔΔG margin.

## Next actions (claim by node, then check off)
- [ ] (Alpha) finish testosterone 2-ligand gate → compare vs 1-ligand; pick survivors.
- [x] (Aspartate) prog/cort gen+screen DONE → leads: prog des0002 (I61L+Q88T); cort des0007 (I61L+Q88T+R123E). See `results/stage3_prog/PROG_CORT_SCREEN_SUMMARY.md`.
- [x] (Aspartate) prog/cort 2-ligand gate DONE. Survivors: prog des0002+des0000 (3/3 pass); cort des0001 only (1/5; top-specificity leads leaky). See `results/stage3_prog/GATE2LIG_SUMMARY.md`.
- [ ] (Aspartate/Beta) ligand-RBFE on gate survivors (prog des0002, cort des0001) for the test/prog/cort triad — the rigorous specificity arbiter.
- [ ] (owner) COMMIT the portable flex-ddG fix (physics_score.py off lcseed + config.py MOLFILE_TO_PARAMS) with the 2-lig scaffold + driver changes.
- [ ] (Alpha) prog/cort FEP/ligand-RBFE.
- [ ] (Beta) build **ligand-ligand RBFE executor** for the test/prog/cort triad → ΔΔΔG specificity (identical A-ring, C17 perturbation maps cleanly; estradiol excluded). This is the rigorous "explain the ΔΔΔG" tool and avoids the E106L second-shell pitfall.
- [ ] (Beta) consider per-position LigandMPNN bias (current `--favor` is uniform across design positions).
