# `prompts/tools/` — tool agents (vs `prompts/personas/` — persona agents)

MiniCrew has two kinds of agent, and they live in two folders:

| | **persona agent** (`prompts/personas/`) | **tool agent** (`prompts/tools/`) |
|---|---|---|
| what it is | a *viewpoint* injected by prompt | a viewpoint **+ the ability to run a real tool** |
| how it answers | reasons from the LLM's knowledge | calls the tool, grounds its answer in real output |
| numbers it gives | "what it believes the value is" | the value the tool actually computed |
| needs | nothing — works today | **tool-calling** (roadmap; the seam is `core/llm.py:call()`) |
| scope | broad (one persona can span many tools) | narrow — scoped to the tool(s) it can actually call |

**Design rule:** group *persona* agents by perspective (a few sharp, distinct
lenses); group *tool* agents by capability (one per tool / tool-cluster, matching
exactly what it can execute). Knowledge stage → merge by viewpoint. Tool stage →
split by capability.

The files here (e.g. `pyrosetta_runner.md`) are **system-prompt drafts for the
tool stage** — they describe the agent that will *run* the tool once tool-calling
lands. Until then, use the matching persona in `prompts/personas/` (e.g.
`structural_energetics.md`) to *reason about* the same tool.
