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
scripts/minicrew distill paper.pdf --si si.pdf --verify -o knowledge/literature/x.md
scripts/minicrew figures paper.pdf --pages 2-4 --model openai   # read figure/table data (vision)
scripts/minicrew-app                                      # web UI in the browser
scripts/minicrew-desktop                                  # same UI in a native window (pywebview)
```

Semantic literature search (optional; needs the DB containers):

```bash
cd minicrew && docker compose up -d && cd ..   # start Mongo + Qdrant
scripts/minicrew index                          # index the .md notes
scripts/minicrew search "aromatic A-ring recognition of estradiol"
```

## The workbench (web / desktop)

`scripts/minicrew-app` (browser) or `scripts/minicrew-desktop` (native window)
open a multipage co-scientist workbench:

- **🔬 Discussion room** — pick a crew, watch the agents review live (streamed),
  then the moderator's synthesis.
- **💬 Chat** — talk 1:1 with one agent, optionally grounded in pitfalls + top-k
  literature (a brainstorm vs the panel).
- **🤖 Agents** — create / edit / delete knowledge & tool agents (role, model,
  system prompt) — no YAML editing.
- **📚 Literature** — ingest papers (PDF / SI / figures), distil, chat-refine,
  cross-check, save & search.
- **🧭 Pipeline** — workflow diagram + live project status + knowledge layers.
- **🗂️ History** — past discussions, each with the exact prompt every agent saw.

Embedder is pluggable (`core/embed.py`, set via `MINICREW_EMBED_BACKEND` in `.env`):

| backend | model | dim | notes |
|---|---|---|---|
| `openai` | text-embedding-3-small | 1536 | API, zero infra |
| `st` | `allenai/specter2_base` | 768 | local SentenceTransformers |
| `specter2` | SPECTER2 + proximity adapter | 768 | **best for papers**; CLS pooling |

Each backend uses its own Qdrant collection, so switching is reversible — just
`index` again. The local backends need extra venv packages:

```bash
# default-PyPI CUDA wheel works; the CPU-index 2.6/2.7 wheels are broken here
minicrew/.venv/bin/pip install torch sentence-transformers adapters
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

## Desktop app

`scripts/minicrew-desktop` runs the Streamlit UI inside a native window
(pywebview) instead of a browser tab — it starts Streamlit headless on a free
port, waits for it, opens the window, and stops the server on close. Run it on a
machine **with a display** that also has the stack (venv + `docker compose up`).

```bash
minicrew/.venv/bin/pip install pywebview          # macOS/Windows: nothing else
# Linux also needs a webview backend:  pip install 'pywebview[qt]'
scripts/minicrew-desktop
```

(`MINICREW_DESKTOP_NOWINDOW=1 scripts/minicrew-desktop` exercises the launch
without a GUI — for headless smoke tests.) Package into a double-click binary
later with PyInstaller.

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
