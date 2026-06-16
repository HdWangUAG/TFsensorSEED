# TFsensorSEED Infrastructure & Deployment

This document tracks the available compute resources for parallel execution of the TFsensorSEED pipeline (PyRosetta flex-ddG and Boltz/FEP).

## Servers Inventory

| Server Alias | IP / Hostname | Hardware (GPU/CPU) | Environment / Role |
| :--- | :--- | :--- | :--- |
| **Node-Alpha** (Main) | `localhost` | 1x RTX 8000, 64-core CPU | `fep` (GROMACS/pmx), `rosetta`. Role: Master node & FEP Target Ligand. |
| **Node-aspartate** (2nd GPU) | `aspartate` | 1x Quadro RTX 6000/8000 (TU102GL), 36-core CPU | conda: `pyrosetta` ✅, `ligandmpnn_env` ✅ (+ `/opt/LigandMPNN` weights), `boltz2` ⚠️ broken, `drMD`. Role: 2nd GPU node — generation + flex-ddG screen + (once envs/GPU fixed) gate. **Brought up 2026-06-16; see PROGRESS.md "Node aspartate".** |
| **Node-Beta** | `[ip_address]` | [Add Hardware] | `rosetta`. Role: flex-ddG batch execution. |
| **Node-Gamma** | `[ip_address]` | [Add Hardware] | `fep`. Role: FEP Decoy Ligands. |

### Node-aspartate bring-up status (2026-06-16)
- **Config:** `.env` written with this node's real paths (LigandMPNN `/opt/LigandMPNN` + `ligandmpnn_env`; PyRosetta `~/.conda/envs/pyrosetta`; Boltz `~/.conda/envs/boltz2`). `config.py` resolves all 5 paths ✅.
- **Verified (CPU):** PyRosetta import ✅, `design_score` (flex-ddG) CLI ✅, `ligandmpnn_gen` import ✅, LigandMPNN `run.py --help` ✅.
- **BLOCKERS (need human / GPU):**
  1. **nvidia driver/library mismatch** — `nvidia-smi` fails (kernel module 580.126.09 vs NVML 580.159). CUDA blocked until modules reloaded or reboot (sudo). All GPU tiers (LigandMPNN sampling, Boltz gate, FEP) wait on this.
  2. **`boltz2` env broken** — depends on `~/.local` user-site (no `click` in-env); `~/.local` matplotlib missing `cycler`. Rebuild self-contained per HANDOFF §2b before the gate can run here.
  3. **No `results/` synced** — only `data/` inputs present. Need rsync of `results/stage1_wt_validation/` (WT holo scaffolds) + any campaign dirs from Alpha (Alpha's address not yet known to this node).

## Storage & Data Sync

*   **Codebase**: Managed via centralized Git repository.
*   **Data/Results**: 
    *   *Option A*: Mounted NFS at `/mnt/shared_tfsensor_data/`
    *   *Option B*: Sync via `rsync` script (`utils/sync_results.sh` - To be implemented)

## Setup Instructions for New Nodes

1. Clone the repository: `git clone [REPO_URL] TFsensorSEED`
2. Install Conda environments:
   - For Tier 1: `conda create -n rosetta ...`
   - For Tier 2: `conda create -n fep -c conda-forge gromacs openmm` + `pip install pmx`
3. Fetch external data: `[Command to fetch large CSVs or DBs not in Git]`
