"""Central, overridable configuration for external tools, model params and envs.

Every path that used to be hardcoded across the pipeline is resolved here, with
this precedence (first match wins):

    1. a process environment variable  (e.g. TFSENSOR_LMPNN_PY=...)
    2. a KEY=VALUE line in a `.env` file at the repo root
    3. a built-in default (the historical path) so a fresh clone still runs

`~` and `$VARS` are expanded everywhere. This lets a container or another user
override every location via `.env` / the environment without editing code.
See `.env.example` for the full list of keys.
"""
from __future__ import annotations

import os

REPO_ROOT = os.path.expanduser(os.environ.get(
    "TFSENSOR_REPO_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _load_dotenv(path):
    vals = {}
    if os.path.isfile(path):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


_DOTENV = _load_dotenv(os.path.join(REPO_ROOT, ".env"))


def get(key, default):
    """Resolve a config key: env var > .env > default, with ~/$VAR expansion."""
    raw = os.environ.get(key, _DOTENV.get(key, default))
    if isinstance(raw, str):
        return os.path.expanduser(os.path.expandvars(raw))
    return raw


# --- external repositories / model weights ---------------------------------
LC_SEED    = get("TFSENSOR_LC_SEED",    "~/LC-Seed")
LMPNN_REPO = get("TFSENSOR_LMPNN_REPO", "~/my_ligandmpnn")
LMPNN_RUN  = get("TFSENSOR_LMPNN_RUN",  os.path.join(LMPNN_REPO, "run.py"))
LMPNN_CKPT = get("TFSENSOR_LMPNN_CKPT",
                 os.path.join(LMPNN_REPO, "model_params/ligandmpnn_v_32_010_25.pt"))

# --- per-task environment interpreters / binaries --------------------------
LMPNN_PY     = get("TFSENSOR_LMPNN_PY",     os.path.join(LC_SEED, "envs/ligandmpnn/.venv/bin/python"))
PYROSETTA_PY = get("TFSENSOR_PYROSETTA_PY", os.path.join(LC_SEED, "envs/pyrosetta/.venv/bin/python"))
BOLTZ_BIN    = get("TFSENSOR_BOLTZ_BIN",    os.path.join(LC_SEED, "envs/boltz2/.venv/bin/boltz"))

# --- ML track (tfsensor/ml/) -----------------------------------------------
# Dedicated GPU venv for the binding-ML work (torch-geometric, ESM-2, captum,
# schnet/torchmd-net). Kept separate from the ligandmpnn env, whose torch is
# pinned to its weights. The plan: ~/.claude/plans/composed-puzzling-church.md
ML_PY        = get("TFSENSOR_ML_PY",        os.path.join(LC_SEED, "envs/ml/.venv/bin/python"))
# Pretrained-scorer baselines (each lives in its own isolated env / binary).
# gnina v1.3.x ships as a self-contained binary; default = the system install.
GNINA_BIN    = get("TFSENSOR_GNINA_BIN",    "/usr/local/bin/gnina")
GEMS_PY      = get("TFSENSOR_GEMS_PY",      os.path.join(LC_SEED, "envs/gems/.venv/bin/python"))
PROLIF_PY    = get("TFSENSOR_PROLIF_PY",    os.path.join(LC_SEED, "envs/prolif/.venv/bin/python"))
# Dataset / cache locations (filled in once acquired; see plan Phase 0).
PDBBIND_DIR  = get("TFSENSOR_PDBBIND_DIR",  os.path.join(REPO_ROOT, "data/ml/pdbbind"))
NRDATA_DIR   = get("TFSENSOR_NRDATA_DIR",   os.path.join(REPO_ROOT, "data/ml/nr_datasets"))
ESM_CACHE_DIR = get("TFSENSOR_ESM_CACHE_DIR", os.path.join(REPO_ROOT, "data/ml/esm_cache"))
