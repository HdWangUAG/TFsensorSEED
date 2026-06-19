"""Configuration + model registry for MiniCrewAI.

Same precedence as tfsensor/config.py — process env > `.env` at repo root >
built-in default — so a container or another user can point every model at a
different endpoint/key without touching code. See `.env.example` for the keys.

A "model alias" (e.g. `claude`, `gemini`, `openai`, `edinburgh`) is what crew
YAML files reference. Each alias resolves to a provider + concrete model id +
the env var(s) that hold its API key (+ optional base_url for self-hosted /
proxied OpenAI-compatible endpoints like the Edinburgh ELM gateway).
"""
from __future__ import annotations

import os

# This file: <repo>/minicrew/src/minicrew/core/config.py
#   _HERE        = .../minicrew/src/minicrew/core
#   MINICREW_DIR = .../minicrew            (the project dir: configs/, prompts/, …)
#   REPO_ROOT    = .../                     (TFsensorSEED — where .env lives)
_HERE = os.path.dirname(os.path.abspath(__file__))
MINICREW_DIR = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))

REPO_ROOT = os.path.expanduser(os.environ.get(
    "TFSENSOR_REPO_ROOT", os.path.dirname(MINICREW_DIR)))


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


def get(key, default=None):
    """Resolve a config key: env var > .env > default, with ~/$VAR expansion.

    An empty value (``KEY=`` in .env or an empty env var) is treated as *unset*
    so a placeholder line never shadows the built-in default for model ids /
    base_urls — fill only the providers you have.
    """
    raw = os.environ.get(key) or _DOTENV.get(key)
    if not raw:
        raw = default
    if isinstance(raw, str):
        return os.path.expanduser(os.path.expandvars(raw))
    return raw


def first_key(*names):
    """Return the first non-empty value among env/.env keys, else None."""
    for n in names:
        v = get(n)
        if v:
            return v
    return None


# --- model registry --------------------------------------------------------
# Each entry: provider, model id, api_key_env (tuple, first set wins), base_url.
# Override the model id per alias via .env (e.g. MINICREW_CLAUDE_MODEL=...).
MODELS = {
    # HTTP API (needs an Anthropic API key — billed separately from any Claude
    # Code subscription). Kept as the reference example of a raw-API provider.
    "claude": dict(
        provider="anthropic",
        model=get("MINICREW_CLAUDE_MODEL", "claude-opus-4-8"),
        api_key_env=("MINICREW_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
        base_url=get("MINICREW_ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
    ),
    # Local `claude` CLI in print mode — uses the Claude Code *subscription*,
    # so NO API key and no per-token API cost. `model` is an optional --model
    # value ("" = whatever the subscription defaults to).
    "claude_cli": dict(
        provider="claude_cli",
        bin=get("MINICREW_CLAUDE_CLI_BIN", "claude"),
        model=get("MINICREW_CLAUDE_CLI_MODEL", ""),
        api_key_env=(),
        base_url="",
    ),
    "gemini": dict(
        provider="gemini",
        model=get("MINICREW_GEMINI_MODEL", "gemini-2.0-flash"),
        api_key_env=("MINICREW_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
        base_url=get("MINICREW_GEMINI_BASE_URL",
                     "https://generativelanguage.googleapis.com/v1beta"),
    ),
    "openai": dict(
        provider="openai",
        model=get("MINICREW_OPENAI_MODEL", "gpt-4o"),
        api_key_env=("MINICREW_OPENAI_API_KEY", "OPENAI_API_KEY"),
        base_url=get("MINICREW_OPENAI_BASE_URL", "https://api.openai.com/v1"),
    ),
    # University of Edinburgh language-model gateway (OpenAI-compatible proxy).
    # Set MINICREW_EDINBURGH_BASE_URL to the ELM /v1 endpoint and the key below.
    "edinburgh": dict(
        provider="openai",
        model=get("MINICREW_EDINBURGH_MODEL", "gpt-4o"),
        api_key_env=("MINICREW_EDINBURGH_API_KEY",),
        base_url=get("MINICREW_EDINBURGH_BASE_URL", ""),
    ),
}


def resolve_model(alias):
    """Return a fully-resolved model spec dict, with `api_key` filled in.

    `api_key` is None when no configured env var holds a value — callers should
    skip such an agent gracefully rather than crash, so a partially-configured
    machine can still run the crew with whatever providers it has.
    """
    if alias not in MODELS:
        raise KeyError(
            f"unknown model alias {alias!r}; known: {', '.join(sorted(MODELS))}")
    spec = dict(MODELS[alias])
    spec["alias"] = alias
    spec["api_key"] = first_key(*spec["api_key_env"])
    return spec


# --- generation defaults (overridable per crew/role) -----------------------
DEFAULT_MAX_TOKENS = int(get("MINICREW_MAX_TOKENS", "1024"))
DEFAULT_TEMPERATURE = float(get("MINICREW_TEMPERATURE", "0.7"))
HTTP_TIMEOUT = int(get("MINICREW_HTTP_TIMEOUT", "180"))

# Project layout (research-style): configs/ prompts/ conversations/ runs/.
CONFIGS_DIR = os.path.join(MINICREW_DIR, "configs")
PROMPTS_DIR = os.path.join(MINICREW_DIR, "prompts")
EXAMPLES_DIR = os.path.join(MINICREW_DIR, "examples")

# Where to look for crew YAML files (configs/ first, then a repo-root override).
CREW_DIRS = [CONFIGS_DIR, os.path.join(REPO_ROOT, "crews")]

# Run outputs: human transcripts + machine records, as top-level project dirs.
OUTPUT_DIR = get("MINICREW_OUTPUT_DIR", MINICREW_DIR)
CONV_DIR = os.path.join(OUTPUT_DIR, "conversations")
RUNS_DIR = os.path.join(OUTPUT_DIR, "runs")

# --- knowledge layer: typed project knowledge with provenance + trust --------
# Each category maps to one or more source dirs/globs. `pitfalls` also pulls the
# repo's curated agent_memory so hard-won lessons ground every discussion.
KNOWLEDGE_DIR = os.path.join(MINICREW_DIR, "knowledge")
KNOWLEDGE_SOURCES = {
    "computational": [os.path.join(KNOWLEDGE_DIR, "computational")],
    "literature":    [os.path.join(KNOWLEDGE_DIR, "literature")],
    "experimental":  [os.path.join(KNOWLEDGE_DIR, "experimental")],
    "pitfalls":      [os.path.join(KNOWLEDGE_DIR, "pitfalls"),
                      os.path.join(REPO_ROOT, "docs", "agent_memory")],
}
# How much each source should sway an agent. Stated verbatim in the prompt.
KNOWLEDGE_TRUST = {
    "experimental":  "HIGH — wet-lab ground truth; overrides model priors and computed numbers",
    "literature":    "HIGH — but verify the applicability domain before transferring a claim",
    "computational": "MEDIUM — a lead, not a verdict; demand uncertainty / replicates",
    "pitfalls":      "HARD CONSTRAINT — known mistakes; do not repeat or re-propose these",
}
