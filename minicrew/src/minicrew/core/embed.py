"""Embeddings — pluggable backend, one seam for the whole system.

  MINICREW_EMBED_BACKEND=openai   text-embedding-3-* over the API (default)
  MINICREW_EMBED_BACKEND=st       local SentenceTransformers model (e.g. SPECTER2)

Both return L2-normalised vectors so Qdrant cosine search is consistent. The
vector dimension changes with the model — switching backends means re-indexing
into the backend-specific collection (config.QDRANT_COLLECTION); the old one
survives for rollback. Swap this file's `st` model for a domain encoder
(SPECTER2 for papers, later ESM2 for sequences) without touching litdb/crew.
"""
from __future__ import annotations

import requests

from . import config

_OPENAI_DIMS = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}
_ST_FALLBACK = "sentence-transformers/allenai-specter"  # native ST SPECTER v1
_st_model = None  # lazy singleton


# --- backend: local SentenceTransformers ------------------------------------
def _load_st():
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer
        try:
            _st_model = SentenceTransformer(config.EMBED_ST_MODEL)
        except Exception:
            # specter2 needs the adapters lib; fall back to the native-ST SPECTER
            _st_model = SentenceTransformer(_ST_FALLBACK)
    return _st_model


def _embed_st(texts):
    model = _load_st()
    vecs = model.encode(list(texts), batch_size=config.EMBED_BATCH,
                        normalize_embeddings=True, convert_to_numpy=True)
    return [v.tolist() for v in vecs]


# --- backend: OpenAI API ----------------------------------------------------
def _embed_openai(texts):
    key = config.first_key("MINICREW_OPENAI_API_KEY", "OPENAI_API_KEY")
    if not key:
        raise RuntimeError("no OpenAI key for embeddings "
                           "(set MINICREW_OPENAI_API_KEY or switch "
                           "MINICREW_EMBED_BACKEND=st)")
    base = config.get("MINICREW_OPENAI_BASE_URL",
                      "https://api.openai.com/v1").rstrip("/")
    r = requests.post(
        base + "/embeddings",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": config.EMBED_MODEL, "input": list(texts)},
        timeout=config.HTTP_TIMEOUT)
    if r.status_code >= 400:
        raise RuntimeError(f"embeddings HTTP {r.status_code}: {r.text[:300]}")
    return [d["embedding"] for d in r.json()["data"]]


# --- public API -------------------------------------------------------------
def embed(texts):
    """Embed a list of strings → list of L2-normalised vectors."""
    if config.EMBED_BACKEND == "st":
        return _embed_st(texts)
    return _embed_openai(texts)


def embed_one(text):
    return embed([text])[0]


def dim():
    """Vector dimension of the active embedder (for collection creation)."""
    if config.EMBED_BACKEND == "st":
        m = _load_st()
        get_dim = (getattr(m, "get_embedding_dimension", None)
                   or m.get_sentence_embedding_dimension)
        return get_dim()
    return _OPENAI_DIMS.get(config.EMBED_MODEL, 1536)


def info():
    """Short description of the active embedder, for logs/CLI."""
    if config.EMBED_BACKEND == "st":
        return f"st:{config.EMBED_ST_MODEL}"
    return f"openai:{config.EMBED_MODEL}"
