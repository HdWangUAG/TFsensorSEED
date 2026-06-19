# MiniCrewAI

A local, config-driven, extensible multi-agent discussion runner for research
projects — a "mini CrewAI". It reads a project's plan / code / data summaries and
has several LLMs (Claude / Gemini / OpenAI / Edinburgh ELM / …) review a task by
role, then a moderator synthesises a decision. Zero heavy deps — only `requests`
+ `pyyaml` (already in the TFsensor conda env).

## Quick start

```bash
# from the repo root — no install needed:
scripts/minicrew models                                   # which providers are ready
scripts/minicrew list                                     # available crews
scripts/minicrew run steroid_plan_review --mock           # full pipeline, 0 tokens
scripts/minicrew run steroid_plan_review --file plan.md    # the real thing
```

Or install once for a global `minicrew` command:

```bash
python3 -m pip install -e .
minicrew run steroid_plan_review --file plan.md
```

## Providers & keys

Keys live in the repo-root `.env` (read by `minicrew/config.py`; see
`.env.example`). Providers without a key are **skipped gracefully** —
`minicrew models` shows ✓/✗ per alias.

| alias        | provider   | needs                                                        |
|--------------|------------|-------------------------------------------------------------|
| `claude_cli` | local CLI  | nothing — uses your Claude Code **subscription** (no API key)|
| `claude`     | HTTP API   | `MINICREW_ANTHROPIC_API_KEY` (billed separately) — reference |
| `openai`     | HTTP API   | `MINICREW_OPENAI_API_KEY` (+ `MINICREW_OPENAI_MODEL`)        |
| `gemini`     | HTTP API   | `MINICREW_GEMINI_API_KEY` (+ `MINICREW_GEMINI_MODEL`)        |
| `edinburgh`  | OpenAI-compat | `MINICREW_EDINBURGH_API_KEY` + `..._BASE_URL` + `..._MODEL`|

> The ELM-issued `sk-svcacct-…` token is a **direct OpenAI key** → use the
> `openai` alias. The `edinburgh` alias is for a real ELM gateway token whose
> base_url is `https://elm.edina.ac.uk/api/v1`.

## Topologies (the design)

Set per-crew with `topology:` (override at runtime with `--topology`):

- **`parallel_blind`** — every reviewer critiques the material *independently*,
  blind to the others; then the moderator surfaces agreement / disagreement.
  Uncorrelated opinions, no anchoring.
- **`round_robin`** — reviewers debate in turn over `rounds:`, each seeing the
  discussion so far; then the moderator closes. A debate that can converge.

The information boundary — who sees what — is the whole point. It lives in
`_reviewer_prompt` / `_round_prompt` / `_moderator_prompt` in `crew.py`.

## Layout

```
minicrew/
├── src/minicrew/          # the package
│   ├── cli.py  __main__.py
│   └── core/              # config, llm, context, crew, logger
├── configs/               # crew definitions (YAML)
├── knowledge/             # typed grounding, by trust tier (a crew opts in via knowledge:)
│   ├── experimental/      #   HIGH — wet-lab ground truth
│   ├── literature/        #   HIGH — distilled paper notes (check domain)
│   ├── computational/     #   MEDIUM — tool capabilities / resolution
│   └── pitfalls/          #   HARD CONSTRAINT — gotchas (+ auto docs/agent_memory)
├── prompts/
│   ├── personas/          # persona agents — viewpoints (work today)
│   └── tools/             # tool agents — persona + real tool-calling (roadmap)
├── examples/              # sample input plans
├── conversations/         # run output — human transcripts (.md)
├── runs/                  # run output — machine records (.json)
├── docs/                  # ARCHIVE.md + the original research scaffold
└── README.md
```

## How it works

- **Model aliases** are defined in `core/config.py` (provider + model id + key envs).
- **Crews** are YAML in `configs/`. A crew has: `topology`, `task`, `context_files`,
  optional `evidence_files` (shown as "more reliable than priors"), `roles`
  (each: a model alias + `persona` inline or `persona_file:` under `prompts/`),
  and an optional `synthesizer`.
- Every run is saved twice (see `core/logger.py`):
  - `conversations/<ts>_<crew>.md` — human transcript, with each agent's reply
    **and** (collapsed) the exact prompt it saw.
  - `runs/<ts>_<crew>.json` — machine record for comparison.

## Add a crew

Copy `configs/steroid_plan_review.yaml`, edit task / roles / personas (or point
`persona_file:` at new files in `prompts/`), then
`minicrew run <your_crew> --file <something>`. Try `--mock` first.

## Roadmap

`llm.call()` is the single seam for every provider, so next steps slot in
cleanly: tool-calling roles (RDKit, ProLIF, Biopython, XGBoost called
mid-review), structured machine-readable verdicts, and a transient-error retry.
