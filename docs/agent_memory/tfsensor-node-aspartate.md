---
name: tfsensor-node-aspartate
description: "TFsensorSEED 2nd GPU node `aspartate` — env layout, what's ready, and the 3 blockers"
metadata: 
  node_type: memory
  type: project
  originSessionId: 31dabd07-532d-4a6b-8d83-7661ef756c67
---

`aspartate` is the 2nd GPU node for TFsensorSEED (joined 2026-06-16), distinct from Node-Alpha (RTX 8000). HW: Quadro RTX 6000/8000, 36-core.

Env layout DIVERGES from HANDOFF.md §2 recipe — there is NO `~/LC-Seed/envs` and NO `~/my_ligandmpnn`. Real paths (written into node-local `.env`, gitignored):
- LigandMPNN: repo+weights `/opt/LigandMPNN` (run.py, ckpt `ligandmpnn_v_32_010_25.pt`), run via `/opt/anaconda3/envs/ligandmpnn_env/bin/python` (torch 2.2.1+cu121).
- PyRosetta (flex-ddG, CPU): `/home/hdwang/.conda/envs/pyrosetta/bin/python` — imports OK.
- Boltz: `/home/hdwang/.conda/envs/boltz2/bin/boltz`.

Ready now (CPU-validated): Tier-0 LigandMPNN gen + Tier-1 flex-ddG screen. LigandMPNN runs on CPU here (`cuda_available False`, clean fallback; 300 seqs→224 designs in seconds; full 1200-seq lib = minutes). Force CPU with `CUDA_VISIBLE_DEVICES=""`.

PLAN (2026-06-16): testosterone done on Alpha; aspartate samples prog/cort/estradiol libraries (CPU) → ship sequences to FEP node for ligand-RBFE. HARD DEP: generation + flex-ddG both need each ligand's WT holo Boltz pose `results/stage1_wt_validation/boltz/seed1/boltz_results_inputs/predictions/wt_<ligand>/wt_<ligand>_model_0.pdb` (gitignored, GPU-made on Alpha). Only the testosterone STR holo (`data/AcrR_STR_001.pdb`) is local. `_build_complex` reuses pre-posed ligand coords — does NOT dock SMILES de novo — so per-ligand poses are mandatory. Unblock = rsync `results/stage1_wt_validation/` from Alpha.

`boltz2` env REPAIRED 2026-06-16: was half-provisioned + leaking into a broken `~/.local`. Fixed via `pip install boltz==2.2.0` in-env (self-contained: torch 2.12.0+cu130, lightning 2.5.0, rdkit, numba); purged a corrupted dual-`dist-info` numpy → 1.26.4 (boltz `<2.0` ∩ numba `<2.2`); patched `bin/boltz` shebang to `python3.10 -s` so it ignores `~/.local` at every driver call site (drivers call the BIN directly, no PYTHONNOUSERSITE). `boltz --help` ✅, `pip check` clean. GPU run still unverified (torch 2.12/cu130 on Turing sm_75 / driver 580).

2 blockers remain (deferred — owner fixes GPU later):
1. `nvidia-smi` driver/library mismatch (kernel 580.126.09 vs NVML 580.159) → CUDA down until module reload/reboot (sudo). Blocks ALL GPU tiers.
2. No `results/` synced from Alpha (only `data/` present); need Alpha's address for rsync of WT scaffolds + campaign dirs.

When taking a GPU campaign here, own a results dir NOT in Alpha's set (gate2lig/prog/cort/fep) to keep merges clean. See [[tfsensor-stage3-pipeline]].
