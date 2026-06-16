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

Ready now (CPU-validated): Tier-0 LigandMPNN gen scaffolding + Tier-1 flex-ddG screen.

3 blockers (deferred — owner fixes GPU later):
1. `nvidia-smi` driver/library mismatch (kernel 580.126.09 vs NVML 580.159) → CUDA down until module reload/reboot (sudo). Blocks ALL GPU tiers.
2. `boltz2` env broken — leaks into `~/.local` user-site (no in-env `click`; `~/.local` matplotlib missing `cycler`). Rebuild self-contained before gate runs here.
3. No `results/` synced from Alpha (only `data/` present); need Alpha's address for rsync of WT scaffolds + campaign dirs.

When taking a GPU campaign here, own a results dir NOT in Alpha's set (gate2lig/prog/cort/fep) to keep merges clean. See [[tfsensor-stage3-pipeline]].
