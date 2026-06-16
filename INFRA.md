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
- **`boltz2` env REPAIRED (2026-06-16):** was half-provisioned (only `boltz`+numpy/scipy/pandas; borrowed torch/click/matplotlib/lightning from a broken `~/.local`). Fixed by `pip install boltz==2.2.0` in-env (self-contained: torch 2.12.0+cu130, pytorch-lightning 2.5.0, rdkit 2026.3.3, numba 0.61), purging a corrupted dual-`dist-info` numpy down to **1.26.4** (boltz `<2.0` ∩ numba `<2.2`), and patching the `bin/boltz` shebang to `python3.10 -s` so it ignores the shared broken `~/.local` at every call site. `boltz --help` exits 0; `pip check` clean. **Still needs a GPU run to confirm** (torch 2.12+cu130 on Turing sm_75 / driver 580 unverified).
- **REMAINING BLOCKERS (need human / GPU):**
  1. **nvidia driver/library mismatch** — `nvidia-smi` fails (kernel module 580.126.09 vs NVML 580.159). CUDA blocked until modules reloaded or reboot (sudo). All GPU tiers (LigandMPNN sampling, Boltz gate, FEP) wait on this.
  2. **No `results/` synced** — only `data/` inputs present. Need rsync of `results/stage1_wt_validation/` (WT holo scaffolds) + any campaign dirs from Alpha (Alpha's address not yet known to this node).

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
