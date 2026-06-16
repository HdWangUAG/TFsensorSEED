# tfsensor_crew — TFsensorSEED status-sync crew

A small CrewAI application that cross-checks the project's two hand-maintained ledgers —
`PROGRESS.md` (campaign narrative) and `JOBS_REGISTRY.csv` (per-node job allocation) — and
emits a synchronization report flagging status mismatches, untracked campaigns/jobs, and
pending next-actions.

**Design note:** the agent/task *structure* is defined in `config/agents.yaml` + `config/tasks.yaml`,
but `crew.kickoff()` runs a **deterministic Python parser** (`parser.py`) for the actual
cross-check — reproducible and free of LLM nondeterminism for what is fundamentally a parse/diff
task. Scope is intentionally the *reporting/consistency layer only*; the scientific compute is
orchestrated by the repo's bash drivers + `JOBS_REGISTRY.csv`, not by LLM agents.

## Install
```bash
cd tfsensor_crew
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"          # crewai + pandas + pyyaml + pytest
```

## Run
```bash
# from the repo root (default paths read PROGRESS.md + JOBS_REGISTRY.csv there):
python -m tfsensor_crew.main --progress ../PROGRESS.md --registry ../JOBS_REGISTRY.csv --output ../sync_report.md
# or the deterministic core directly (no crewai needed):
python -c "from tfsensor_crew.parser import *; ..."
```

## Test
```bash
pytest tests/        # 61-test suite (F1–F5 feature coverage + boundary + pairwise + real-world)
```

## Docs
- `PROJECT.md` — architecture, milestones, interface contracts.
- `TEST_INFRA.md` — test philosophy, feature inventory, coverage thresholds.
- `TEST_READY.md` — test-suite readiness checklist.
