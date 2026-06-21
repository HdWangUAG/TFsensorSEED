"""MiniCrewAI — a lightweight, config-driven multi-agent discussion runner.

A research-oriented "mini CrewAI": read a project's plan/code/data summaries,
let several LLMs (Claude / Gemini / OpenAI / Edinburgh ELM / ...) debate a task
by role, then have a moderator synthesise a decision. Zero heavy deps — only
`requests` + `pyyaml`, which the TFsensor envs already ship.

Entry point: `python -m minicrew run <crew> --file plan.md` (or the `./minicrew`
shim at the repo root).
"""

__version__ = "0.1.0"
