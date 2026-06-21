# MiniCrew on Windows — the simple "desktop app" setup

Your heavy backend (torch/CUDA, SPECTER2, Mongo+Qdrant, API keys) lives on the
Linux node. Rather than re-install all of that on Windows, keep the backend on
the node and put a thin **app window** on your PC. Daily use = double-click an
icon → the MiniCrew window opens. No Python on Windows.

## How it works (who runs where)

```
┌─────────────────────────┐        ┌────────────────────────────────────────┐
│   Your Windows PC        │        │      Linux GPU node (server)           │
│                          │        │                                        │
│  double-click            │        │  ┌─ Streamlit web app (port 8501) ───┐ │
│   MiniCrew.bat           │        │  │  = the UI you see + Python backend │ │
│     ↓                    │  port  │  │   · distill (calls Claude/GPT)     │ │
│  Edge app window  ───────┼────────┼─→│   · crew discussions               │ │
│  → localhost:8501        │ forward│  │   · SPECTER2 embeddings (torch/GPU)│ │
│                          │        │  └──────────┬─────────────────────────┘ │
│  (nothing else here —    │        │             │ read / write              │
│   no Python, no data)    │        │  ┌──────────┴──── Docker ────────────┐ │
│                          │        │  │  MongoDB  ← note text + metadata   │ │
│                          │        │  │  Qdrant   ← SPECTER2 vectors       │ │
│                          │        │  └────────────────────────────────────┘ │
└─────────────────────────┘        └────────────────────────────────────────┘
```

- **The `.bat` is just a remote control** — it opens a window pointing at the
  node. It starts nothing on the server and stores nothing on your PC.
- **The server does all the work and holds all the data.** Uploaded PDFs are sent
  to the server, processed there (the raw PDF isn't kept — only the distilled
  `.md` note is saved, under `minicrew/knowledge/literature/` on the node).
  Vectors live in Qdrant, full text + metadata in MongoDB — both on the node
  (`minicrew/.data/`). Your Windows PC keeps **only the `.bat` file**.
- **What must stay up to keep using it:** the Streamlit app + the port forward
  (and the Docker containers, for search). The Edge window itself you can close
  and reopen any time — double-click again. If the SSH/VS Code connection drops,
  the forward dies; just reconnect.

## What Docker is for

Docker runs two databases **on the server**: **MongoDB** (note text + metadata)
and **Qdrant** (the SPECTER2 vectors for semantic search). It's just an easy way
to run those two services without installing them by hand (`docker compose up -d`
starts them, `down` stops them; data persists in `minicrew/.data/`).

It is **only needed for the literature index + semantic search** (and a
discussion that retrieves papers). Distilling a paper, chat-refining a note, and
running a discussion work fine **without** Docker.

## One-time setup
1. **Backend on the node** — start the UI and the databases there:
   ```bash
   cd ~/TFsensorSEED && (cd minicrew && docker compose up -d) && scripts/minicrew-app
   ```
   Leave that running (a terminal/`tmux`).
2. **Port forwarding to your PC** — so `localhost:8501` on Windows reaches the
   node's Streamlit:
   - **VS Code Remote-SSH**: automatic (you'll see 8501 in the PORTS tab), **or**
   - **Plain SSH** from a Windows terminal:
     ```
     ssh -L 8501:localhost:8501 <user>@<node>
     ```
     (keep it open while using the app)
3. **The launcher** — copy `minicrew/desktop/MiniCrew.bat` to your PC (e.g. the
   Desktop). Right-click → *Send to → Desktop (create shortcut)* if you want an
   icon; set a custom icon via the shortcut's Properties → Change Icon.

## Daily use
- Make sure step 1 (backend) and step 2 (forwarding) are up.
- **Double-click `MiniCrew.bat`** → a clean app window opens (Edge app mode).
  If the backend isn't reachable it tells you what to start.

## If you'd rather run *everything* on Windows (fully local, offline)
That's possible but a much bigger setup: install Python + the venv deps (torch
CUDA, sentence-transformers, adapters, streamlit, pywebview, pymongo,
qdrant-client), Docker Desktop (for Mongo+Qdrant), and a `.env` with your keys —
then `scripts/minicrew-desktop` opens the real native window locally. Only worth
it if you need it offline / away from the node.
