# `pitfalls/` — development gotchas / lessons (避坑点)

Hard-won "do not repeat this" knowledge — trust tier **HARD CONSTRAINT**. Agents
are told not to re-propose anything that contradicts a pitfall.

This category **already auto-includes the repo's curated `docs/agent_memory/`**
(see `core/config.py:KNOWLEDGE_SOURCES`), so every lesson recorded there grounds
discussions without copying. Add project-specific gotchas that don't belong in
agent_memory directly here as `.md` files (one lesson each):

```
---
title: <short lesson>
trust: HARD CONSTRAINT
tags: [scoring, gate, generation]
---
## What went wrong
## Why
## The rule going forward
```
