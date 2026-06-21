# Archive — `minicrew-research/`

`minicrew-research/` was the original research-demo scaffold (LiteLLM-based,
`parallel-blind then synthesize` topology, external prompts, prompt-logging).

**It is superseded.** Every idea worth keeping has been merged into the main,
zero-dependency `minicrew/` package one level up:

| research idea | where it now lives in `minicrew/` |
|---|---|
| parallel-blind topology + information boundary | `crew.py` (`_reviewer_prompt` / `_moderator_prompt`), `topology: parallel_blind` |
| round-robin debate (new) | `crew.py` (`_round_prompt`), `topology: round_robin` |
| mock mode | `--mock` flag (`cli.py`, `crew.py:_mock_reply`) |
| log the exact prompt each agent saw | `logger.py` (`prompt_seen` in both .md and .json) |
| external persona files | `prompts/*.md` + `persona_file:` in crew YAML |
| evidence / grounding slot | `evidence_files:` in crew YAML → `_material()` |
| example plan fixture | `examples/steroid_project/plan.md` |

Kept here for reference only — not imported, not on the run path. The live tool
is `scripts/minicrew` → the `minicrew/` package. See `minicrew/README.md`.
