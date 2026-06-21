# MiniCrew agents — capabilities & limitations

A quick reference for what each agent **can** do and what it **cannot** — so you
weight their output correctly. Agents are LLM personas (`minicrew/prompts/personas/`),
not tools or oracles.

## ⚠️ Limitations that apply to EVERY agent

These are properties of the system, not of any one persona:

1. **They read only curated *markdown text*, not raw data.** Each run injects the
   crew's `context_files` / `evidence_files` (e.g. `PROGRESS.md`, `LAB_MANUAL.md`,
   `DEV_STATUS.md`) + the `knowledge/` notes + `docs/agent_memory/`. They do **not**
   parse `results/*.json`, `*.csv`, PDB/SDF, or the ML manifests. A number reaches an
   agent only if it is written into the injected markdown.
2. **No code execution / no DB queries** — except the Chat page's **🛠️ Tools** toggle,
   which lets an agent call real **RDKit** functions (OpenAI function-calling) for
   descriptors/similarity. In a **Discussion (crew)** there are **no tools** — pure
   reasoning over the injected text.
3. **Context is truncated** (`MINICREW_MAX_CHARS_PER_FILE`) — very large files are cut.
4. **No memory between runs** except what you **sediment** into `knowledge/`
   (discussion→`decisions/`, chat→`engineering/`).
5. **They are reviewers, not ground truth.** Their job is to critique, triage, and
   surface blind spots — not to produce experimental numbers. Trust tiers in the
   prompt say so: experimental/literature > computational > model priors.

## The agents

| Agent | Model | Capabilities (功能) | Limitations (局限) |
|---|---|---|---|
| **Structural Biologist** | claude_cli | Pocket geometry, H-bond networks, **allostery / binding→activation coupling** for TetR/AcrR; finds the mechanistic reason a design fails | Reasons from *described* geometry — can't open a PDB, inspect a real pose, or run MD; no access to coordinates |
| **Structural Energetics** | openai (gpt-5.5) | Critiques every **number-producing method**: Rosetta flex-ddG, Boltz apo/holo gate, FEP/RBFE; flags any value **below method resolution** | Can't run the calculations or recompute; only sees numbers that are in the injected text |
| **Cheminformatics** | claude_cli | Ligand recognition & **selectivity**: H-bond pattern, aromaticity, pKa/tautomer/protonation, decoys, ordered water; ProLIF/RDKit-style geometric triage | Qualitative geometry, **not an affinity oracle**; can't generate/verify 3D poses; only runs real RDKit in Chat with 🛠️ Tools on |
| **ML / Statistics** | claude_cli | **Data leakage**, domain-shift (NR→AcrR), funnel-stage independence, **calibration / gate thresholds**, validation design | Can't run the validations it proposes; sees only metrics present in the text; no access to raw splits/data |
| **PI / Moderator** | claude_cli | Synthesises independent reviews → agreement / disagreement / **least-verifiable claim** / prioritised must-fix list | No privileged truth; only as good as the reviewers; can flag but not resolve a shared blind spot |

## How to give them more to work with
- Add a file to a crew's `context_files`/`evidence_files` (LAB_MANUAL is now injected).
- Upload "Extra material" in the Discussion room for a one-off.
- Write results into a `knowledge/experimental/*.md` note (HIGH trust) — the proper
  home for wet-lab ground truth.
