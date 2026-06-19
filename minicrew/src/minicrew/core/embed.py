"""Text embeddings via the OpenAI embeddings API (reuses the OpenAI/ELM key).

One HTTP call, no SDK — same spirit as llm.py. Used to index literature notes
into Qdrant and to embed search queries.
"""
from __future__ import annotations

import requests

from . import config


def embed(texts):
    """Embed a list of strings → list of vectors (list[float])."""
    key = config.first_key("MINICREW_OPENAI_API_KEY", "OPENAI_API_KEY")
    if not key:
        raise RuntimeError("no OpenAI key for embeddings "
                           "(set MINICREW_OPENAI_API_KEY)")
    base = config.get("MINICREW_OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    r = requests.post(
        base + "/embeddings",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": config.EMBED_MODEL, "input": texts},
        timeout=config.HTTP_TIMEOUT)
    if r.status_code >= 400:
        raise RuntimeError(f"embeddings HTTP {r.status_code}: {r.text[:300]}")
    return [d["embedding"] for d in r.json()["data"]]


def embed_one(text):
    return embed([text])[0]
