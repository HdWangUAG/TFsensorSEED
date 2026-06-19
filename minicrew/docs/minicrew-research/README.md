# MiniCrew (research demo)

Multi-agent review for a steroid-sensor ML project. Topology: **parallel-blind
then synthesize** — two reviewers critique independently, a moderator surfaces
agreement/disagreement for a human to adjudicate.

## Run the smoke test (no API keys, free)
    cd src
    python -m minicrew.demo --file ../examples/steroid_project/plan.md --mock

## Run for real
    pip install litellm
    export ANTHROPIC_API_KEY=...   GEMINI_API_KEY=...
    cd src
    python -m minicrew.demo --file ../examples/steroid_project/plan.md

Then point --file at your REAL plan.md / code / results.

## What to read
- `core/crew.py`  — the design lives here. `reviewer_prompt` vs
  `moderator_prompt` encode the information boundary. Change them, change the system.
- `conversations/*.md` — each agent's reply AND the prompt it saw. Your microscope.

## Built / deferred
Built: Context, parallel-blind Crew, transcript+json logger, critical-by-design prompts.
Deferred (hooks in place): `evidence` slot for paper/assay grounding, sequential
topology to compare against, CLI flags, file/git tools, safety lists.
