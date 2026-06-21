# Running MiniCrew on another server (fresh setup)

The repo holds all code, configs, prompts, and knowledge notes. Three things are
gitignored and must be recreated on the new machine: **`.env`** (keys),
**`minicrew/.venv`** (Python env), **`minicrew/.data`** (the DB volumes — rebuilt
from the `.md` notes).

## 0. System prerequisites
- `git`, Python ≥ 3.10
- **Docker** + `docker compose` (for Mongo + Qdrant; optional — only literature
  search needs it)
- **poppler-utils** (`pdftotext`, `pdftoppm`) for PDF distill + figure vision
- Internet on first run (SPECTER2 ~440 MB + adapter download from HuggingFace)
- Optional: the **`claude`** CLI logged in, if you want the `claude_cli` provider
  (subscription, no API key). Otherwise use API-key providers (below).

## 1. Clone
```bash
git clone https://github.com/HdWangUAG/TFsensorSEED.git
cd TFsensorSEED && git checkout node-aspartate
```

## 2. Keys — create `.env`
```bash
cp .env.example .env      # then edit
```
Set the providers you'll use (any subset):
```ini
MINICREW_OPENAI_API_KEY=sk-...          # enables `openai` + tool-calling + (optional) OpenAI embeddings
MINICREW_GEMINI_API_KEY=...             # enables `gemini`
MINICREW_ANTHROPIC_API_KEY=sk-ant-...   # enables the `claude` HTTP provider
MINICREW_EMBED_BACKEND=specter2         # local SPECTER2 (no key); = openai needs an OpenAI key
```
> The bundled crews use `claude_cli` for some roles. Without the `claude` CLI on
> this machine, either install/login it, or switch those roles to `openai`/`gemini`
> in the **Agents/Crews** pages (or edit `minicrew/configs/*.yaml`).

## 3. Python env (`minicrew/.venv`)
```bash
python3 -m venv minicrew/.venv
# install torch FIRST from the DEFAULT PyPI index (CUDA wheel; the CPU-index
# 2.6/2.7 wheels are broken on the aspartate node — a clean server may not need this):
minicrew/.venv/bin/pip install torch
minicrew/.venv/bin/pip install -r minicrew/requirements.txt
```

## 4. Start + build the index
```bash
scripts/minicrew-start        # Mongo + Qdrant + web app → http://localhost:8501
# in another shell (first time, to populate the vector index from the .md notes):
scripts/minicrew index
```

## 5. Use it
- Web: `scripts/minicrew-app` (or the all-in-one `scripts/minicrew-start`)
- CLI: `scripts/minicrew models` / `list` / `run <crew>` / `tool "…"` / `sediment`
- Desktop window (needs a display): `scripts/minicrew-desktop`

## Sanity checks
```bash
scripts/minicrew models       # ✓/✗ per provider
scripts/minicrew list         # crews present
scripts/minicrew run steroid_plan_review --mock   # full pipeline, 0 tokens
```
