# MiniCrew Structure

MiniCrew is a local, config-driven multi-agent research workbench. Its current
role in this repository is to help the TFsensor project run structured scientific
discussions, call selected computational tools, save the complete run record, and
sediment useful conclusions into long-term project memory.

At a high level, MiniCrew is built around this loop:

```text
Scientist / user
  -> CLI or Streamlit UI
  -> crew orchestrator
  -> role-specific prompts
  -> LLM agents
  -> optional tool_request blocks
  -> deterministic skill execution
  -> transcript + JSON run record
  -> optional typed memory sedimentation
  -> future recall/context
```

## Entry Points

MiniCrew can be used from the command line or from the Streamlit workbench.

- `scripts/minicrew` is the main no-install CLI launcher. It sets
  `PYTHONPATH=minicrew/src` and runs `python -m minicrew`.
- `scripts/minicrew-app` launches the Streamlit web UI.
- `scripts/minicrew-start` starts the supporting database containers and the UI.
- `scripts/minicrew-stop` stops the database containers.
- `minicrew/src/minicrew/cli.py` defines the CLI subcommands.
- `minicrew/app/Home.py` is the Streamlit app entry point.

Common commands:

```bash
scripts/minicrew list
scripts/minicrew models
scripts/minicrew skills
scripts/minicrew run structure_probe --mock --rounds 1
scripts/minicrew-app
```

## Configuration Layer

Crews are YAML configuration files in `minicrew/configs/`.

Each crew defines:

- `name`: crew identifier.
- `task`: the scientific question or review target.
- `topology`: discussion pattern, usually `round_robin` or `parallel_blind`.
- `rounds`: number of discussion rounds for round-robin.
- `context_files`: optional source files injected into the prompt.
- `evidence_files`: higher-trust evidence injected separately.
- `knowledge`: knowledge categories to recall or inject.
- `tools`: allowed skills for the deterministic `tool_request` path.
- `roles`: reviewer agents, their model aliases, personas, and limits.
- `synthesizer`: optional moderator role.

Persona prompts live under `minicrew/prompts/personas/`. A role can either define
an inline `persona:` or reference a `persona_file:`.

**Agents vs skills (the boundary):**

- `prompts/personas/` — **persona agents**: scientific viewpoints/roles (system
  prompts). No code; they reason.
- `skills/` — **runnable tools** and their capability docs (PyMOL, flex-ddG,
  RDKit, literature…), the single source of truth for real computation. See
  `core/skills.py`, `core/skills_impl.py`, `minicrew/skills/skills.yaml`.
- `prompts/tools/` has been **removed** — "tool agents as prompt files" is gone;
  computational capabilities are skills, not personas.

The configuration layer is intentionally simple: adding a new crew should usually
mean adding one YAML file and possibly one persona prompt.

## Core Orchestrator

The discussion engine is `minicrew/src/minicrew/core/crew.py`.

It is responsible for:

- loading crew YAML files;
- building context and knowledge blocks;
- assembling prompts for reviewers and moderators;
- enforcing prompt-size budgets;
- calling the selected LLM provider;
- detecting and executing tool requests;
- appending compact tool results to the transcript;
- saving each run through `logger.save_run()`;
- optionally invoking `scribe` to sediment the run into typed memory.

The two main discussion topologies are:

- `parallel_blind`: reviewers see the task and evidence independently, then the
  moderator synthesizes.
- `round_robin`: reviewers speak in sequence and see previous turns.

The current prompt boundary is implemented in:

- `_reviewer_prompt()`
- `_round_prompt()`
- `_moderator_prompt()`
- `_material()`
- `_discussion_so_far()`

This boundary is important. It determines what each agent can see, and therefore
whether opinions are independent, anchored, or debate-aware.

## Model Layer

Model dispatch lives in `minicrew/src/minicrew/core/llm.py`.

Supported provider shapes:

- `claude_cli`: local Claude Code subscription through the `claude` CLI.
- `anthropic`: Anthropic Messages API.
- `openai`: OpenAI-compatible chat completions, including local gateway aliases.
- `gemini`: Google Gemini API.

Model aliases and defaults live in `minicrew/src/minicrew/core/config.py`.

Important current behavior:

- `claude_cli` receives the user prompt over stdin, not argv. This avoids OS argv
  size limits and avoids exposing long prompts in process listings.
- OpenAI and newer reasoning-style models get provider-specific token parameter
  handling.
- Missing API keys are handled as readable `LLMError` messages rather than raw
  tracebacks.

## Prompt Budgeting

MiniCrew now measures assembled prompts before model calls.

Relevant config:

```text
MINICREW_PROMPT_WARN_CHARS
MINICREW_PROMPT_MAX_CHARS
```

Default behavior:

- warn above `PROMPT_WARN_CHARS`;
- fail fast above `PROMPT_MAX_CHARS`;
- allow a crew to override with `max_prompt_chars:`;
- allow explicit opt-in with `allow_large_prompts: true`.

This is a guard against unbounded context growth from large project files,
knowledge notes, literature, and prior discussion content.

Known gap:

- prompt budgeting currently applies to real/mock runs, but dry-run prompt
  preview should also be made budget-aware.
- the CLI should return a nonzero exit code when prompt budgeting aborts a run.

## Tool And Skill Layer

MiniCrew has two tool paths.

### Deterministic Crew Tool Requests

Crew agents can request tools by emitting a fenced block:

````text
```tool_request
skill: analyze_structure
args:
  pdb_path: data/AcrR_STR_001.pdb
  ligand_resname: STR
reason: inspect actual pocket contacts before judging orientation
```
````

The runtime path is:

```text
agent reply
  -> toolrun.parse_requests()
  -> allow-list check
  -> toolrun.execute()
  -> skills.call()
  -> compact SkillResult appended to transcript
  -> full artifact written under minicrew/artifacts/
```

This path works with non-native tool-calling agents such as `claude_cli` because
the LLM only writes a structured request. MiniCrew executes the skill
deterministically.

### OpenAI Native Function Calling

`minicrew/src/minicrew/core/toolcall.py` implements an OpenAI-compatible
function-calling loop. It is used by the chat/tool path rather than by default
crew discussion.

This path uses:

- `tools.openai_schemas()`
- `tools.REGISTRY`
- OpenAI-compatible model tool calls

### Skill Framework

The modern skill framework lives in:

- `minicrew/src/minicrew/core/skills.py`
- `minicrew/src/minicrew/core/skills_impl.py`
- `minicrew/skills/skills.yaml`

`skills.py` provides:

- skill registration;
- argument validation;
- preflight checks;
- subprocess execution helpers;
- timeouts;
- heavy-tool budgeting;
- artifact/provenance structure;
- standard `SkillResult` objects;
- OpenAI schema generation.

`skills_impl.py` contains the concrete scientific capabilities, including:

- RDKit ligand descriptors and similarity;
- ProLIF interaction fingerprints;
- XGBoost model training;
- PyMOL structure analysis;
- pocket mutation visualization;
- flex-ddG scoring;
- Boltz comparison;
- retrodiction;
- literature search.

`tools.py` remains as a compatibility shim for older chat/CLI paths. New crew
code should prefer `skills.call()`.

## Knowledge And Memory Layer

MiniCrew's long-term memory is markdown-based and lives under
`minicrew/knowledge/`.

Important categories:

- `literature/`: distilled paper notes.
- `experimental/`: wet-lab or high-trust experimental facts.
- `computational/`: computational method notes and boundaries.
- `claims/`: typed scientific claims.
- `evidence/`: typed evidence records.
- `decisions/`: project decisions and moderator conclusions.
- `pitfalls/`: recurring constraints, caveats, and failure modes.

Core modules:

- `knowledge.py`: assembles knowledge blocks for crew prompts.
- `memory.py`: creates, parses, writes, and supersedes typed records.
- `kdb.py`: searches typed records with metadata/status filtering.
- `scribe.py`: extracts claims, decisions, and pitfalls from run records.
- `context_pack.py`: role-specific context packing path for future tighter recall.

Typed records are markdown files with YAML frontmatter. Common fields include:

```yaml
id: dec_...
type: decision
tags: [...]
status: active
confidence: medium
source_run: ...
superseded_by: ...
supersession_note: ...
```

Memory lifecycle is important:

- new computational tool output should start as `candidate`;
- normal recall should prefer active records;
- superseded or rejected records should not be deleted silently;
- retractions and supersessions should stay auditable.

## Run Outputs

Each crew run is saved in two forms:

- `minicrew/conversations/<run_id>.md`: human-readable transcript.
- `minicrew/runs/<run_id>.json`: machine-readable record.

The Markdown transcript contains each agent's visible reply plus the exact prompt
that agent saw.

The JSON record contains structured outputs, prompt hashes, and actual output
paths. It is used by history views, comparison, and sedimentation.

Tool artifacts are written under:

```text
minicrew/artifacts/
```

This directory is ignored by git. Curated evidence and memory records should be
stored in `minicrew/knowledge/`, not only in transient artifacts.

## Streamlit Workbench

The UI lives under `minicrew/app/`.

Key pages:

- `discussion.py`: run a crew and stream turns.
- `chat.py`: one-on-one agent chat, optionally with tool support.
- `history.py`: inspect previous run records and reports.
- `skills.py`: inspect and run registered skills.
- `agents.py`: manage agent definitions.
- `crews.py`: assemble crews.
- `literature.py`: ingest, distill, and search literature.
- `pipeline.py`: project workflow/status overview.

The UI is a convenience layer over the same core modules used by the CLI.

## Current Development State

The current implementation has these major pieces working:

- crew loading and listing;
- model alias readiness checks;
- mock runs;
- prompt assembly and transcript saving;
- skill registration and basic skill execution;
- deterministic `tool_request` support in crew discussions;
- typed memory records;
- run sedimentation path;
- Streamlit workbench pages;
- minimal pure-stdlib regression tests.

Recently fixed:

- Claude CLI now receives prompts through stdin.
- run saving now reports actual Markdown and JSON paths.
- supersession notes are persisted in typed memory.
- prompt size budgets are enforced before model calls.
- `minicrew_ui.pid` is ignored as a runtime file.

Known issues to address next:

- CLI prompt-budget aborts should exit nonzero.
- dry-run should also check prompt budgets.
- `start_all_bg.sh` should be replaced or hardened; prefer maintained launchers.
- `memory.py` should close files with `with open(...)` to remove
  `ResourceWarning`s.
- generated run artifacts and curated knowledge records need a clear git policy.

## Mental Model For Contributors

When changing MiniCrew, keep these boundaries in mind:

```text
configs/ + prompts/
  define who the agents are and what task they discuss

crew.py
  controls what each agent can see and when each turn happens

llm.py
  is the only provider-dispatch layer for text/vision model calls

skills.py + skills_impl.py
  own real computational capabilities and provenance

toolrun.py
  lets crew agents request deterministic skills

tools.py + toolcall.py
  preserve the legacy/OpenAI-native tool-calling path

knowledge.py + memory.py + kdb.py + scribe.py
  own long-term recall, typed records, and sedimentation

logger.py
  owns persistent run records

app/
  is UI over the same core APIs
```

The most important design principle is that MiniCrew should not turn uncertain
LLM text directly into trusted project fact. Agent output, tool output, and
memory records must remain auditable, status-tagged, and tied back to provenance.
