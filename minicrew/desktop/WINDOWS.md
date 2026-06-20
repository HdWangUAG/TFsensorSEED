# MiniCrew on Windows — the simple "desktop app" setup

Your heavy backend (torch/CUDA, SPECTER2, Mongo+Qdrant, API keys) lives on the
Linux node. Rather than re-install all of that on Windows, keep the backend on
the node and put a thin **app window** on your PC. Daily use = double-click an
icon → the MiniCrew window opens. No Python on Windows.

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
