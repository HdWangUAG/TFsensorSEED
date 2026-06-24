# MiniCrew — Handover & Onboarding Guide

> **Who this is for:** anyone taking over or learning MiniCrew from scratch.
> Read this top-to-bottom once; after that it's a reference. It assumes no prior
> knowledge of the codebase, only basic Python + shell.
>
> **The other docs, and when to read them:**
> - [`README.md`](README.md) — day-to-day usage cheat-sheet (commands, UI pages).
> - [`SETUP.md`](SETUP.md) — installing on a fresh machine (env, keys, DBs).
> - [`docs/MINICREW_STRUCTURE.md`](docs/MINICREW_STRUCTURE.md) — the deep
>   architecture reference (module-by-module).
> - [`docs/AGENTS.md`](docs/AGENTS.md) — what each science persona can/can't do.
> - [`docs/ARCHIVE.md`](docs/ARCHIVE.md) — history of the pre-package prototype.

---

## 1. What MiniCrew is (in one minute)

MiniCrew is a **local, config-driven, multi-agent research workbench**. You point
it at a research task plus some project files, and several LLMs (Claude / OpenAI /
Gemini / a university gateway / the local Claude CLI) **review the task by role**
— a structural biologist, a cheminformatician, an ML/stats reviewer, etc. — and a
**moderator synthesises** their independent critiques into a prioritised, must-fix
verdict. It can also **run real computational skills** (PyMOL, flex-ddG, RDKit,
Boltz…) mid-discussion, and **remember** useful conclusions across runs.

It lives inside the **TFsensor** project, whose science goal is engineering an
AcrR/TetR-family transcription factor into a **steroid biosensor** with tuned
ligand **selectivity** (e.g. estradiol over progesterone/cortisol/testosterone).
That's why the bundled crews and knowledge talk about pockets, ΔΔG, poses, and
selectivity. MiniCrew itself is **domain-agnostic** — the science is all in
config + knowledge files, not in the code.

**What MiniCrew is NOT:**

- Not an autonomous agent that edits your repo or runs experiments on its own.
- Not a source of ground truth. Agents are **reviewers**; they reason over text
  you give them. A number only reaches an agent if it's written into injected
  markdown.
- Not a heavyweight framework. The core is plain Python with only `requests` +
  `pyyaml` required; everything else (DBs, ML libs) is optional.

**The single most important design principle** (keep it in mind for every change):

> MiniCrew must never turn uncertain LLM text directly into trusted project fact.
> Agent output, tool output, and memory records stay **auditable, status-tagged,
> and tied to provenance**.

---

## 2. The 10-minute tour (zero tokens, no keys)

From the repo root. `--mock` runs the entire pipeline with canned replies, so it
costs nothing and needs no API keys:

```bash
scripts/minicrew models                       # which providers are configured (✓/✗)
scripts/minicrew list                         # the available crews
scripts/minicrew skills                       # the runnable computational skills
scripts/minicrew run structure_probe --mock --rounds 1   # full loop, fake replies
```

Then open the UI (also works offline):

```bash
scripts/minicrew-app                          # → http://localhost:8501
```

When you're ready for a real run with real models, set keys (see §8) and drop
`--mock`:

```bash
scripts/minicrew run steroid_plan_review --file examples/steroid_project/plan.md
```

---

## 3. The mental model

Everything is one loop:

```text
Scientist
  → CLI (scripts/minicrew) or Streamlit UI (scripts/minicrew-app)
  → crew orchestrator (core/crew.py)         # loads the crew YAML
  → role-specific prompts (the "information boundary")
  → LLM agents (core/llm.py)                  # one provider-dispatch seam
  → optional ```tool_request``` blocks
  → deterministic skill execution (core/skills.py)
  → transcript (.md) + machine record (.json) (core/logger.py)
  → optional sedimentation into typed memory (core/scribe.py)
  → future recall feeds back into prompts (knowledge.py / kdb.py / context_pack.py)
```

When you change MiniCrew, hold these **four boundaries** separate — most bugs come
from blurring them:

| Boundary | Owns | Files |
|---|---|---|
| **Who the agents are** | personas + crew definitions | `prompts/personas/`, `configs/*.yaml` |
| **What each agent sees, and when** | prompt assembly, topology, turn order | `core/crew.py` |
| **How models are called** | provider dispatch (the only place) | `core/llm.py` |
| **Real computation + memory** | skills, knowledge, typed records | `core/skills*.py`, `core/knowledge.py`, `core/memory.py`, `core/kdb.py`, `core/scribe.py` |

---

## 4. Repository map

```
minicrew/
├── src/minicrew/
│   ├── cli.py            # all CLI subcommands (run, distill, recall, promote, …)
│   ├── __main__.py       # `python -m minicrew`
│   └── core/
│       ├── config.py     # model registry, paths, knowledge trust tiers, budgets
│       ├── crew.py       # the discussion engine + prompt boundary
│       ├── llm.py        # provider dispatch (anthropic/openai/gemini/claude_cli) + vision
│       ├── context.py    # inject context_files / evidence_files (truncated)
│       ├── knowledge.py  # assemble the "flat" knowledge block (trust-tier labelled)
│       ├── context_pack.py # role-specific, budgeted, status-filtered recall (opt-in)
│       ├── kdb.py        # search typed records (metadata filter + semantic/keyword rank)
│       ├── memory.py     # typed records: make / parse / write / supersede / promote
│       ├── scribe.py     # sediment a run → decisions note + typed records
│       ├── skills.py     # skill framework (registration, validation, budgets, artifacts)
│       ├── skills_impl.py# the concrete skills (PyMOL, flex-ddG, RDKit, Boltz, …)
│       ├── toolrun.py    # crew-side ```tool_request``` parsing + allow-list + execute
│       ├── toolcall.py   # OpenAI native function-calling loop (chat path)
│       ├── logger.py     # save each run as .md transcript + .json record
│       ├── litdb.py / litstore.py / embed.py   # literature index (Mongo + Qdrant + embeddings)
│       └── verify.py     # adversarial claim-checking before sedimenting
├── app/                  # Streamlit UI (Home.py + pages/*) — thin layer over core/
├── configs/              # crew definitions (YAML) — 5 bundled crews
├── prompts/personas/     # persona agents (scientific viewpoints) — 12 bundled
├── skills/               # skill catalog (md) + scripts/ — the home for runnable tools
├── knowledge/            # long-term memory, by category + trust tier (see §6.3)
├── examples/             # sample input plans (fixtures)
├── conversations/        # run output — human transcripts (.md)   [generated]
├── runs/                 # run output — machine records (.json)   [generated]
├── artifacts/            # skill outputs (PNGs, scores)           [generated, gitignored]
├── tests/                # pure-stdlib regression tests (no pytest needed)
├── docker-compose.yml    # Mongo + Qdrant (only literature search needs them)
└── README.md / SETUP.md / HANDOVER.md / docs/
```

Three things are **gitignored and must be recreated per machine** (see SETUP.md):
`.env` (keys), `minicrew/.venv` (Python env), `minicrew/.data` (DB volumes,
rebuilt from the `.md` notes).

---

## 5. The CLI surface

`scripts/minicrew <subcommand>` (no install needed — it puts `minicrew/src` on
`PYTHONPATH`). The subcommands:

| Command | What it does |
|---|---|
| `models` | show each model alias and whether its key is set (✓/✗) |
| `list` | list available crews |
| `skills` | list runnable skills (`--write` regenerates the catalog) |
| `run <crew>` | run a discussion. Flags: `--mock`, `--dry-run`, `--rounds N`, `--file F`, `--topology`, `--out PATH`, `--sediment` |
| `distill <paper>` | turn a paper PDF/text into a distilled `knowledge/literature/` note (`--si`, `--verify`, `-o`) |
| `figures <paper>` | read figure/table data from PDF pages via a vision model |
| `sediment [run_id]` | extract a run's decisions/claims/pitfalls into typed memory (default: latest run) |
| `recall [query]` | retrieve typed records. Filters: `--type`, `--tag`, `--confidence`, `--status`, `--include-superseded`, `-k` |
| `supersede <id>` | mark a record superseded (`--by <new_id>`, `--note`) — keeps the reversal auditable |
| `promote [id]` | **vet a `candidate` record into `active`** so it's recalled (no id → list pending). `--to`, `--note` |
| `index` | (re)index literature notes + typed records into Mongo + Qdrant |
| `search <query>` | semantic search over the literature index |
| `tool "<request>"` | run a single skill from the CLI |

---

## 6. Core concepts in depth

### 6.1 Crews & topologies

A **crew** is a YAML file in `configs/`. It declares the task, which reviewer
**roles** (each = a model alias + a persona), an optional **synthesizer**
(moderator), what **knowledge** to recall, and what **skills** are allowed. The
**topology** decides the information boundary:

- **`parallel_blind`** — every reviewer critiques the material *independently*,
  blind to the others; the moderator then surfaces agreement/disagreement.
  Opinions are uncorrelated → no anchoring.
- **`round_robin`** — reviewers speak in turn over `rounds:`, each *seeing* the
  discussion so far; the moderator closes. A debate that can converge.

The boundary lives in three functions in `crew.py`: `_reviewer_prompt` (blind),
`_round_prompt` (sees peers), `_moderator_prompt` (sees all reviews). **Change
those and you change the system's character.** Every turn records `prompt_seen`
— the exact text that agent received — so a transcript always explains *why* it
said what it said.

### 6.2 Personas (agents) vs Skills (tools) — the boundary

This distinction matters and was recently cleaned up:

- A **persona agent** (`prompts/personas/*.md`) is a *viewpoint*: a system prompt
  that makes an LLM reason as, say, a structural biologist. **No code. It reasons.**
- A **skill** (`skills/` + `core/skills_impl.py`) is a *real runnable capability*:
  PyMOL analysis, flex-ddG scoring, RDKit descriptors, Boltz folding. **It computes.**

There used to be a `prompts/tools/` ("tool agents as prompt files") concept — it's
**gone**. Runnable capability = skill, not a persona. The UI reflects this: the
**Agents** page manages personas; the **Skills** page manages skills.

A crew agent invokes a skill by emitting a fenced `tool_request` block; the runtime
(`toolrun.py`) parses it, checks the crew's allow-list, executes deterministically
(`skills.call()`), and appends a compact result to the transcript so later agents
see real numbers. This works even for non-tool-calling models (e.g. `claude_cli`)
because the LLM only *writes a request* — MiniCrew does the running.

### 6.3 Knowledge layers & trust tiers

Long-term grounding lives under `knowledge/`, one folder per **category**, each
with a **trust tier** stated verbatim in the prompt (so agents weigh wet-lab over
model priors). Defined in `config.py` (`KNOWLEDGE_SOURCES` / `KNOWLEDGE_TRUST`):

| Category | Trust tier | What's in it |
|---|---|---|
| `experimental/` | **HIGH** — ground truth | wet-lab methods + results |
| `literature/` | **HIGH** — check applicability domain | distilled paper notes |
| `computational/` | **MEDIUM** — a lead, not a verdict | method capabilities/limits |
| `decisions/` | **MEDIUM** — revisit if data conflicts | prior decisions / moderator conclusions |
| `engineering/` | **MEDIUM** — tactical know-how | gotchas sedimented from 1:1 chats |
| `claims/` | **MEDIUM** — weigh by status + evidence | typed scientific claims |
| `evidence/` | **MEDIUM** — coarse compute ≠ truth | typed computational/literature evidence |
| `pitfalls/` | **HARD CONSTRAINT** — do not repeat | known mistakes / failure modes |

A crew opts in via `knowledge: [pitfalls, decisions, …]` in its YAML.

### 6.4 Typed memory & its lifecycle

`claims / evidence / decisions / pitfalls` are **typed records**: markdown files
with YAML frontmatter (`id, type, status, confidence, tags, source_run, …`),
created by `memory.py` and usually **auto-sedimented** by `scribe.py` after a run
(if the crew sets `auto_sediment: true` or you pass `--sediment`).

`status` gates recall (`kdb.py`). The lifecycle:

```text
candidate ──promote──▶ active/open/supported ──supersede──▶ superseded
(hidden)               (recalled into prompts)              (hidden, but auditable)
```

- **`candidate`** — not recalled. Auto-extracted pitfalls and raw tool evidence
  start here, so an LLM-guessed "rule" can't silently become a HARD CONSTRAINT.
- **active / open / supported / mixed** — recalled into discussions.
- **superseded / rejected / expired** — hidden by default, never silently deleted.

The **human vetting gate** is the `promote` command:

```bash
minicrew promote                       # list candidates awaiting review
minicrew promote pit_1a2b3c4d --note "confirmed in the L147R campaign"
```

Reversals use `supersede` (keeps both the old and the link to its replacement).
Both write a note into frontmatter (`promotion_note` / `supersession_note`) for
the audit trail.

### 6.5 Retrieval — two paths, and `top_k`

When a crew assembles a prompt, growing knowledge is **retrieved, not dumped**:

- **Flat path** (`knowledge.build`, default): typed categories + literature are
  retrieved by relevance when a query exists; curated categories
  (`pitfalls/computational/experimental/engineering`) inject whole files. **This
  path also pulls `docs/agent_memory/` into `pitfalls`.**
- **Context-pack path** (`context_pack.build_pack`, when a crew sets
  `context_pack: true`): a **role-specific, budgeted, status-filtered** briefing.
  Different roles get different slices (the Skeptic even sees superseded
  decisions; the Tool-Runner gets almost nothing). ⚠️ **Caveat:** this path reads
  typed records only from `knowledge/<dir>`, so `docs/agent_memory/` is *not*
  pulled in. If a context-pack crew needs those lessons, convert them to typed
  `pitfalls/` records.

**`top_k`** = "keep only the most-relevant *k* records." Implemented two ways
(`kdb.py` / `litdb.py`): typed records are metadata-filtered, then ranked (cosine
if the vector DB is up, else keyword overlap) and **sliced `[:k]`**; literature
uses Qdrant's server-side `limit=k`. A min-score threshold (`LIT_MIN_SCORE`) then
drops "filler" hits, so fewer than *k* may actually appear.

### 6.6 Prompt budgeting

Assembled prompts are measured before every model call (`crew._prompt_guard`):

- **warn** above `MINICREW_PROMPT_WARN_CHARS` (default 100k),
- **fail fast** above `MINICREW_PROMPT_MAX_CHARS` (default 500k),
- override per crew (`max_prompt_chars:` / `allow_large_prompts: true`) or via env.

A budget abort prints a clear `error:` and exits **nonzero**. This guards against
unbounded context growth as `knowledge/` accumulates.

---

## 7. Recipes (end-to-end workflows)

### Run a discussion
```bash
scripts/minicrew run steroid_plan_review --mock --rounds 1     # rehearse, 0 tokens
scripts/minicrew run steroid_plan_review --file plan.md         # real run
# outputs: conversations/<run>.md (transcript) + runs/<run>.json (record)
```

### Ingest a paper into literature
```bash
scripts/minicrew distill paper.pdf --si si.pdf --verify -o knowledge/literature/x.md
scripts/minicrew index                                          # make it searchable
scripts/minicrew search "aromatic A-ring recognition of estradiol"
```

### Curate memory after runs
```bash
scripts/minicrew sediment                 # sediment the latest run (if not auto)
scripts/minicrew recall --status candidate --type pitfall      # see what's pending
scripts/minicrew promote pit_xxxx --note "verified"            # gate it into active
```

### Add a new crew
Copy `configs/steroid_plan_review.yaml`, edit `task` / `roles` (model alias +
`persona_file:`) / `knowledge` / `synthesizer`. `minicrew run <crew> --mock` to
test. (Or build it in the **Crews** UI page.)

### Add a new persona
Drop a markdown file in `prompts/personas/` (optional YAML frontmatter for
`name`/`model`/`description`, body = the system prompt), then reference it from a
crew role's `persona_file:`. (Or use the **Agents** UI page.)

### Add a new skill
Implement it in `core/skills_impl.py`, register it in `skills.py` /
`skills/skills.yaml` (args schema, preflight, timeout, heavy-budget flag), then
add it to a crew's `tools:` allow-list. `scripts/minicrew skills --write`
regenerates the catalog.

---

## 8. Providers & keys

Keys live in the repo-root `.env` (see `.env.example`). Missing providers are
**skipped gracefully** — `minicrew models` shows ✓/✗.

| alias | provider | needs |
|---|---|---|
| `claude_cli` | local CLI | nothing — your Claude Code **subscription** (no API key) |
| `claude` | Anthropic API | `MINICREW_ANTHROPIC_API_KEY` (billed separately) |
| `openai` | OpenAI API | `MINICREW_OPENAI_API_KEY` |
| `gemini` | Gemini API | `MINICREW_GEMINI_API_KEY` |
| `edinburgh` | OpenAI-compatible gateway | `MINICREW_EDINBURGH_API_KEY` + `..._BASE_URL` |

`llm.call()` is the **single seam** for every text/vision provider — add a new
provider there and nowhere else.

---

## 9. Operational gotchas

- **Agents read curated markdown, not raw data.** They don't parse `*.json`,
  `*.csv`, PDB/SDF. Numbers must be written into injected markdown to be seen.
- **No memory between runs** except what you sediment + promote into `knowledge/`.
- **`context_pack: true` skips `docs/agent_memory/`** (see §6.5).
- **Databases are optional.** distill/chat/discuss work without Docker; only
  literature *search* needs Mongo + Qdrant.
- **Generated vs curated files.** `conversations/`, `runs/`, `artifacts/` are
  generated; `knowledge/` records are curated. Decide a git policy before
  committing run outputs in bulk (`artifacts/` is already gitignored).
- **`claude_cli` runs in a cleaned env** so a nested Claude Code session doesn't
  make the child behave as a sub-agent; the prompt is passed on **stdin**.

---

## 10. Testing & dev checks

No pytest needed — tests are pure-stdlib `unittest`:

```bash
minicrew/.venv/bin/python -m compileall -q minicrew/src minicrew/app minicrew/tests
minicrew/.venv/bin/python -m unittest discover -s minicrew/tests
scripts/minicrew list && scripts/minicrew skills
```

`tests/test_core.py` covers the high-risk pure logic: supersede/promote gating,
logger paths, memory round-trip. Add to it when you touch `memory.py` /
`logger.py` / `kdb.py`.

---

## 11. Glossary

- **Crew** — a YAML-defined team of reviewer roles + a moderator for one task.
- **Topology** — the information boundary (`parallel_blind` vs `round_robin`).
- **Persona** — an LLM viewpoint (system prompt); reasons, no code.
- **Skill** — a real runnable computational capability; computes.
- **Knowledge / trust tier** — grounding material, weighted by source reliability.
- **Typed record** — a markdown+frontmatter memory item (claim/evidence/decision/pitfall).
- **Sediment** — extract durable records from a finished run.
- **Promote / supersede** — the human gates that move a record's `status`.
- **`top_k`** — keep the *k* most-relevant retrieved records.
- **`prompt_seen`** — the exact text an agent received, logged for auditability.

---

*Start with §2 (the 10-minute tour), keep §3 (the mental model) in your head, and
reach for `docs/MINICREW_STRUCTURE.md` when you need module-level detail.*
