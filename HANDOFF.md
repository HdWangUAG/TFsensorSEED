# TFsensorSEED — cross-server handoff & merge guide

Master doc for moving development to another node and merging back. Pairs with:
- `PROGRESS.md` — live campaign state & what's running where (update this as you go).
- `docs/agent_memory/` — the agent's accumulated knowledge (mirror of `~/.claude/.../memory/`).
- `INFRA.md` — node inventory (fill in IPs/hardware).

---

## 0. TL;DR — what actually travels, and how

| Bucket | Contents | Transport | Mergeable? |
|---|---|---|---|
| **Code** | `tfsensor/`, `*.sh`, `tfsensor/config.py` | **git** | yes (text) |
| **Docs/memory** | `*.md`, `docs/agent_memory/` | **git** | yes (text) |
| **Inputs** | `data/` (panel, FASTA, AcrR PDBs), WT holo poses under `results/stage1_wt_validation/` | **rsync once** | no (static) |
| **Results** | everything else under `results/` (Boltz preds, MD traj, screens) | **rsync per-campaign** | no — partition by node |
| **Envs** | conda `fep`, `~/LC-Seed/envs/*`, `~/my_ligandmpnn` weights | **rebuild per node** (§2) | n/a |

> ⚠️ `.gitignore` excludes `results/`, `data/`, `.claude/`, and all `*.pdb/*.log/*.xtc/...`.
> So **git alone does NOT carry inputs, results, or (originally) the agent memory.** That's why
> the memory is mirrored into `docs/agent_memory/` and inputs/results move by rsync.

> ⚠️ **There is currently no git remote.** Before you can clone on another node:
> `git remote add origin <url> && git push -u origin master` (or transfer by `git bundle` / rsync of the repo).

---

## 1. Bring-up on a new node (checklist)

1. **Repo:** `git clone <url> TFsensorSEED` (or rsync the repo dir).
2. **Inputs (rsync, ~6 MB + poses):**
   ```
   rsync -av <alpha>:~/TFsensorSEED/data/ ~/TFsensorSEED/data/
   rsync -av <alpha>:~/TFsensorSEED/results/stage1_wt_validation/ ~/TFsensorSEED/results/stage1_wt_validation/
   ```
   (the WT holo poses `wt_<ligand>_model_0.pdb` are the scaffolds every campaign reads.)
3. **Envs:** rebuild per §2 (don't rsync conda envs across different hardware/CUDA).
4. **Config:** `cp .env.example .env` and edit the paths for this node (see `tfsensor/config.py`).
   Verify: `python -c "from tfsensor import config; print(config.LMPNN_RUN, config.BOLTZ_BIN)"`.
5. **Smoke:** `python -m tfsensor.design_score panel --help` and `conda run -n fep gmx -version | grep GPU`.

---

## 2. Environment recipe (THE one that works — supersedes INFRA.md §Setup)

### 2a. `fep` conda env — Tier-2 FEP (GROMACS + pmx + acpype)
The traps below each cost us a debugging cycle; do it in this order:

```bash
conda create -n fep -c conda-forge python=3.10 openmm -y
# GROMACS: MUST pin the CUDA build. The conda-forge default is OpenCL-only and reports
# "no GPU detected" on NVIDIA cards.
conda install -n fep -c conda-forge "gromacs=2025.4=nompi_cuda_h39c90b0_0" -y
# AmberTools (antechamber/sqm backend for acpype) + acpype + openbabel.
# GOTCHA: install ambertools TOGETHER WITH the pinned CUDA gromacs — a later solve
# that touches gromacs will silently drop ambertools/acpype AND revert gromacs to OpenCL.
conda install -n fep -c conda-forge ambertools "gromacs=2025.4=nompi_cuda_h39c90b0_0" -y
conda run -n fep pip install acpype          # pip 'acpype' (the conda one also works)
# pmx: build from the develop branch. `pip install pmx` is a PYTHON-2 package — do NOT use it.
git clone -b develop https://github.com/deGrootLab/pmx.git ~/pmx_src
conda run -n fep pip install --no-build-isolation ~/pmx_src   # --no-build-isolation: setuptools clash
```
Verify (all three must be true):
```bash
conda run -n fep bash -lc 'gmx -version | grep "GPU support"'      # -> CUDA  (not OpenCL)
conda run -n fep bash -lc 'which antechamber acpype'                # both present
conda run -n fep python -c "import pmx; print(pmx.__file__)"
```
Runtime env for pmx mutation FF: `export GMXLIB=$CONDA_PREFIX/lib/python3.10/site-packages/pmx/data/mutff`; mutant FF = `amber99sb-star-ildn-mut`.

### 2b. `~/LC-Seed/envs/*` (uv/pip venvs) — used by Tiers 0/1/1.5
- `ligandmpnn/.venv` — LigandMPNN (GPU). Needs `~/my_ligandmpnn/run.py` + `model_params/ligandmpnn_v_32_010_25.pt`.
- `pyrosetta/.venv` — flex-ddG screen (CPU).
- `boltz2/.venv` — Boltz-2 cofolding (GPU).
- `app/.venv` — RDKit + matplotlib + scipy (ligand prep, figures, analysis).
Reproduce from each env's lockfile, or rsync `~/LC-Seed/envs` + `~/my_ligandmpnn` if hardware/CUDA match.

### 2c. MD landmines already encoded in `run_rbfe_general.sh` (don't re-discover)
- `genion` group selection must be **SOL** (not the ion name).
- The pmx hybrid residue **detonates at dt=2 fs** → ladder is **EM(emtol 100) → restrained NVT (dt=1 fs, −DPOSRES) → NPT**.
- `gmx trjconv -skip` counts **frames**, not steps.
- Boltz conda build OpenCL→CUDA caveat is the same as GROMACS above.

---

## 3. Live job state (Node-Alpha = localhost, RTX 8000) — DO NOT duplicate elsewhere

These are GPU-bound on Alpha and **will not migrate**; let them finish here:

| Job | Dir | Driver / monitor | Status |
|---|---|---|---|
| Testosterone 2-ligand gate (all 71) | `results/stage3_dring/gate2lig/` | `drive_gate2lig.sh` / monitor `bi0bzsoei` | running (~9.5 h) → writes `GATE2LIG_DONE` + `gate2lig.json` |
| Prog + cort gen + flex-ddG screen | `results/stage3_prog/`, `results/stage3_cort/` | `drive_prog_cort.sh` / monitor `bxwn7zxi1` | queued (waits for the gate to free GPU) → `results/stage3_prog_cort_DONE` |

Not yet started (need leads first): prog/cort 2-ligand gates; ligand-RBFE (test/prog/cort triad) for ΔΔΔG.

---

## 4. Suggested job allocation (avoid collisions = clean merge)

Partition by **result directory ownership** so no two nodes write the same path:

| Node | Owns (authoritative results dirs) | Work |
|---|---|---|
| **Alpha** (GPU, RTX 8000) | `results/stage3_dring/gate2lig`, `results/stage3_prog`, `results/stage3_cort`, `results/stage3_fep` | finish GPU campaigns: gates, generation, FEP/RBFE |
| **Beta** (the dev node) | `tfsensor/` code, `docs/`, new analysis/harness modules | build the **ligand-RBFE (ΔΔΔG) executor**, analysis & figures, doc upkeep; optional CPU flex-ddG batches into a *separate* dir |

Rule: a campaign's `results/<dir>/` is owned by exactly one node. Code/docs are shared via git.

---

## 5. Merge-back procedure

1. **Code/docs/memory (git):** dev node works on a branch (`git switch -c dev-beta`), commits, pushes; merge to `master` (text-only, conflicts trivial). Re-sync `docs/agent_memory/` into the dev node's `~/.claude/.../memory/` so its agent inherits context (and copy any *new* memory back out before merging).
2. **Results (rsync):** because each node owns distinct `results/<campaign>/` dirs, pull each owner's dirs to the canonical store — no overwrite conflicts:
   ```
   rsync -av <beta>:~/TFsensorSEED/results/<beta-owned>/  ~/TFsensorSEED/results/<beta-owned>/
   ```
3. **PROGRESS.md** is the reconciliation ledger — each node updates its section; merge is a text merge.

---

## 5b. Reusable executors → `scripts/` (tracked)
The FEP & gate executors were written under `results/` (gitignored), so canonical copies now
live in **`scripts/fep/`** and **`scripts/gate/`** (tracked): `run_rbfe_general.sh` (env-driven
RBFE leg), `drive_specificity.sh`, `prep_ligands.py`, `analyze_specificity.py`,
`make_fep_demo_figure.py`, `run_rbfe_l147r_demo.sh`, `drive_gate2lig.sh`.
> ⚠️ These still contain **hardcoded `/home/hdwang/...` paths** (they predate `config.py`).
> Adjust per node, or route them through `tfsensor/config.py` before reuse elsewhere.

## 6. What still needs a human decision (not yet done)
- [ ] Create the git **remote** and push (`git remote add origin … && git push -u origin master`).
- [ ] Fill `INFRA.md` Node-Beta/Gamma IPs + hardware.
- [ ] Decide transport for `data/` + WT poses (rsync vs commit the ~6 MB inputs to git).
- [ ] Confirm `~/LC-Seed/envs` + `~/my_ligandmpnn` can be rsync'd (same CUDA) or must be rebuilt.
