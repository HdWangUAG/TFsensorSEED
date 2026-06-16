# TFsensorSEED

Engineering the **AcrR** transcription factor into **steroid-specific allosteric biosensors**
(GFP fluorescence = derepression). Computational design + first-principles structural reasoning,
validated against wet-lab assays.

> **Scope:** computation predicts **affinity/specificity**; allosteric **amplitude** is a
> qualitative check and ultimately a **wet-lab** readout. See `docs/`/`LAB_MANUAL.md` for why.

## Start here
| You want… | Read |
|---|---|
| Current status / what's running where | **`PROGRESS.md`** + **`JOBS_REGISTRY.csv`** |
| Move to / set up another node | **`HANDOFF.md`** (env recipe, git/rsync split, merge) |
| The science: design rules & ground truths | **`LAB_MANUAL.md`** |
| Pipeline architecture (4 tiers) | **`PIPELINE.md`** |
| Dev history / milestones | **`DEV_STATUS.md`** |
| Compute nodes | **`INFRA.md`** |
| Agent context (accumulated knowledge) | **`docs/agent_memory/`** |

## Pipeline (4 tiers)
**Tier 0** motif-anchored LigandMPNN generation → **Tier 1** PyRosetta flex-ddG specificity screen
→ **Tier 1.5** Boltz 2-state geometry gate (apo/holo, *2-ligand*) → **Tier 2** FEP / ligand-RBFE
(pmx + GROMACS non-equilibrium TI). Honest caveat baked in: specificity isn't resolvable to
~1 kcal/mol on predicted poses, and the amplitude gate is a single-predictor proxy — final calls
combine gate ∩ empirical-scan convergence + wet-lab.

## Repo layout
```
tfsensor/            Python library (config.py routes all paths via .env)
scripts/             reusable executors — fep/ (RBFE), gate/ (2-ligand gate)
tfsensor_crew/       CrewAI status-sync tool (PROGRESS.md ↔ JOBS_REGISTRY.csv linter)
docs/                agent_memory/ + design notes
data/                small static inputs (panel, FASTA, AcrR structures)  [tracked]
results/             pipeline outputs   [gitignored — rsync between nodes]
deliverables/        wet-lab handoff sheets (FASTA + mutations + caveats)
drive_*.sh           stage drivers
PROGRESS.md JOBS_REGISTRY.csv   live ledgers (kept at root; the crew reads them)
```

## Setup
Per-node bring-up (envs, inputs) is in **`HANDOFF.md §1–2`** — note the `fep` env needs a
**CUDA-pinned GROMACS** + pmx-from-git + ambertools (the obvious `pip install pmx` / plain conda
recipe is wrong). Copy `.env.example`→`.env` and edit paths for the node.

## Status crew
```bash
cd tfsensor_crew && python3.12 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
python -m tfsensor_crew.main --progress ../PROGRESS.md --registry ../JOBS_REGISTRY.csv --output ../sync_report.md
```
(Requires Python 3.10–3.12 — crewai does not support 3.13+. The deterministic core in
`parser.py` runs on any Python.)
