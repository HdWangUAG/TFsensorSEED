# Project: TFsensorSEED Status Crew

## Architecture
A standalone CrewAI application designed to aggregate status information from the TFsensorSEED pipeline:
- Input files:
  - `PROGRESS.md` (root directory)
  - `JOBS_REGISTRY.csv` (root directory)
- Processing:
  - CrewAI agents parsing markdown and CSV data.
  - Combines campaign status and registry tasks to report synchronization/discrepancies.
- Output:
  - Synchronization report summarizing pipeline status.

## Code Layout
The project follows the standard CrewAI directory structure in the `/home/hdwang/TFsensorSEED/tfsensor_crew` folder:
- `tfsensor_crew/`
  - `src/`
    - `tfsensor_crew/`
      - `__init__.py`
      - `crew.py` (Agents, Tasks, and Crew setup)
      - `main.py` (Entrypoint script for execution)
      - `config/`
        - `agents.yaml` (Agent definitions)
        - `tasks.yaml` (Task definitions)
  - `knowledge/` (Knowledge source files)
  - `tests/` (Unit/Integration test files)
  - `pyproject.toml` (Poetry dependency and package configuration)
  - `README.md`

## Milestones
| # | Name | Scope | Dependencies | Status | Conv ID |
|---|------|-------|-------------|--------|---------|
| 1 | E2E Testing Setup | Initialize E2E test suite and write TEST_INFRA.md | None | DONE | fc5993c3-8db6-4602-b3f5-2ac09104fc81 |
| 2 | CrewAI Initialization | Setup project skeleton, configuration, and pyproject.toml | M1 | DONE | d8b77f5e-b826-4950-93a0-3beb78d856b8 |
| 3 | Crew Implementation | Implement agents, tasks, and main entry points | M2 | DONE | 6aa0496e-da6a-4b38-b1a4-12bbffa0c2d8 |
| 4 | Verification & Hardening | Run E2E tests, white-box adversarial tests, and forensic audit | M3 | DONE | 85588d99-f3bb-46ce-a48c-6794f875c630, 843dfac0-90ed-40f2-8863-5535b0bca8da |

## Interface Contracts
### CLI Entrypoints
- Running `crewai run` inside `tfsensor_crew/` directory must execute the crew.
- Alternatively, running `python src/tfsensor_crew/main.py` (or through poetry) must execute the crew.
- Output format: Markdown report containing sections for Campaign Status and Job Registry synchronization.
