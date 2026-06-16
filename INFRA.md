# TFsensorSEED Infrastructure & Deployment

This document tracks the available compute resources for parallel execution of the TFsensorSEED pipeline (PyRosetta flex-ddG and Boltz/FEP).

## Servers Inventory

| Server Alias | IP / Hostname | Hardware (GPU/CPU) | Environment / Role |
| :--- | :--- | :--- | :--- |
| **Node-Alpha** (Main) | `localhost` | 1x RTX 8000, 64-core CPU | `fep` (GROMACS/pmx), `rosetta`. Role: master; running testosterone 2-ligand gate + FEP/RBFE. |
| **Node-Aspartate** | `129.215.109.43` (hdwang@, key auth OK) | GPU node | `ligandmpnn` + `rosetta`. Role: **prog / cort / estradiol generation + flex-ddG screen** (reassigned from Alpha 2026-06-16). Has `data/` + `results/stage1_wt_validation/` (rsync'd). |
| **Node-Beta** (dev) | `[ip_address]` | [Add Hardware] | Role: development (ligand-RBFE ΔΔΔG executor, analysis); code via git. |

## Storage & Data Sync

*   **Codebase + docs + agent-memory + `data/`**: git — `https://github.com/HdWangUAG/TFsensorSEED`.
*   **Inputs (WT holo poses) + Results**: **rsync** (gitignored, large). Example (Alpha→Aspartate, done 2026-06-16):
    `rsync -avz results/stage1_wt_validation hdwang@129.215.109.43:~/TFsensorSEED/results/`
*   No NFS in use; per-node ownership of `results/<campaign>/` dirs avoids merge conflicts (see `HANDOFF.md §4–5`).

## Setup Instructions for New Nodes

⚠️ **The authoritative, tested bring-up recipe is `HANDOFF.md §1–2`** (the old `pip install pmx` /
`conda … gromacs openmm` recipe was wrong — pip pmx is Python-2; GROMACS must be CUDA-pinned; ambertools
must be installed *with* gromacs). In brief:
1. `git clone https://github.com/HdWangUAG/TFsensorSEED` ; `cp .env.example .env` (edit paths).
2. rsync `data/` (or git now carries it) + `results/stage1_wt_validation/` WT poses.
3. Build envs per `HANDOFF.md §2` (`fep` = CUDA GROMACS + pmx-from-git + ambertools/acpype; `~/LC-Seed/envs/*`).
