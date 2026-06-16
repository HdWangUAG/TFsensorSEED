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
  Made self-contained (`pip install boltz==2.2.0`: torch 2.12.0+cu130, lightning 2.5.0, rdkit,
  numba), purged a corrupted dual numpy → 1.26.4, patched `bin/boltz` shebang to `-s` (ignore
  user-site) so it works at every driver call site. `boltz --help` ✅, `pip check` clean. Tier-1.5
  gate is code-ready here; only a GPU run remains to confirm torch 2.12/cu130 on this Turing card.
- **Blocked (deferred per owner):** (1) `nvidia-smi` driver/library mismatch → CUDA down until
  driver reload/reboot (sudo; owner will do later) — blocks all GPU tiers. (2) no `results/`
  synced from Alpha yet (need Alpha's address for rsync of WT scaffolds + campaign dirs).
- **Ready to take a GPU campaign once (1)+(2)+(3) clear.** Must own a results dir NOT owned by
  Alpha (gate2lig/prog/cort/fep are Alpha's per §4) to keep merges clean — assignment TBD with owner.


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
| **Progesterone** | gen+screen | **queued** (Alpha) | `results/stage3_prog/` | design: ligand-aware D-ring + mild S/T/N/Q (C20=O) bias, keep A-ring |
| **Cortisol** | gen+screen | **queued** (Alpha) | `results/stage3_cort/` | design: **R123E anchor** + polar D-ring (S/T/N/Q) |

## Wet-lab panel (current best, build-and-test)
Testosterone: **des0039 / des0060 / des0044** (I61L+L85I) + single **E106L**. Cortisol: **R123E** (validated) + forthcoming cortisol designs. Judge by gate + FEP + wet-lab, NOT the ΔΔG margin.

## Next actions (claim by node, then check off)
- [ ] (Alpha) finish testosterone 2-ligand gate → compare vs 1-ligand; pick survivors.
- [ ] (Alpha) finish prog/cort gen+screen → ranked leads.
- [ ] (Alpha) prog/cort 2-ligand gate on leads; FEP/ligand-RBFE.
- [ ] (Beta) build **ligand-ligand RBFE executor** for the test/prog/cort triad → ΔΔΔG specificity (identical A-ring, C17 perturbation maps cleanly; estradiol excluded). This is the rigorous "explain the ΔΔΔG" tool and avoids the E106L second-shell pitfall.
- [ ] (Beta) consider per-position LigandMPNN bias (current `--favor` is uniform across design positions).
