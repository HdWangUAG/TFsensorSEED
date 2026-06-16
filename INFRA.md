# TFsensorSEED Infrastructure & Deployment

This document tracks the available compute resources for parallel execution of the TFsensorSEED pipeline (PyRosetta flex-ddG and Boltz/FEP).

## Servers Inventory

| Server Alias | IP / Hostname | Hardware (GPU/CPU) | Environment / Role |
| :--- | :--- | :--- | :--- |
| **Node-Alpha** (Main) | `localhost` | 1x RTX 8000, 64-core CPU | `fep` (GROMACS/pmx), `rosetta`. Role: Master node & FEP Target Ligand. |
| **Node-Beta** | `[ip_address]` | [Add Hardware] | `rosetta`. Role: flex-ddG batch execution. |
| **Node-Gamma** | `[ip_address]` | [Add Hardware] | `fep`. Role: FEP Decoy Ligands. |

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
