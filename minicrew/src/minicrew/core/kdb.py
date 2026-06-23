"""Knowledge DB — one retrieval interface over typed records, layout hidden.

Generalizes litdb (literature-only, vector-required) to ALL typed memory
(claims / evidence / decisions / pitfalls) with a single call:

    kdb.search(query, types=["pitfall","decision"], tags=["selectivity"],
               confidence_min="medium", include_superseded=False, top_k=10)

Hybrid + degrade-gracefully (the reviewer's requirement): metadata + keyword
filtering over the on-disk records ALWAYS works (no DB needed); when the vector
DB is up + indexed, semantic ranking is layered on top. Default retrieval HIDES
superseded records (so a reversed decision doesn't resurface as if still live).
"""
from __future__ import annotations

import re

from . import config, memory

_WORD = re.compile(r"[a-z0-9]+")


def db_available():
    try:
        from . import litdb
        ok, _ = litdb.status()
        return ok
    except Exception:
        return False


def _filter(records, tags=None, confidence_min=None, status=None,
            include_superseded=False):
    out = []
    cmin = memory.CONF_RANK.get(confidence_min, -1) if confidence_min else -1
    for r in records:
        st = r.get("status")
        if status is not None:
            if st != status:               # explicit status query (e.g. candidates)
                continue
        else:
            # default: only ACTIVE — hide candidate/superseded/rejected/expired
            # (tool evidence is candidate until vetted). Skeptic passes
            # include_superseded to also see reversals.
            hidden = memory.INACTIVE_STATUS - ({"superseded"} if include_superseded else set())
            if st in hidden:
                continue
        if cmin >= 0 and memory.CONF_RANK.get(r.get("confidence", "medium"), 1) < cmin:
            continue
        if tags and not (set(t.lower() for t in tags) & set(
                str(t).lower() for t in (r.get("tags") or []))):
            continue
        out.append(r)
    return out


def _keyword_rank(query, records, top_k):
    q = set(_WORD.findall((query or "").lower()))
    if not q:
        return records[:top_k]
    scored = []
    for r in records:
        hay = set(_WORD.findall(
            (r.get("text", "") + " " + " ".join(map(str, r.get("tags") or []))).lower()))
        overlap = len(q & hay)
        tag_bonus = len(q & set(str(t).lower() for t in (r.get("tags") or [])))
        scored.append((overlap + 0.5 * tag_bonus, r))
    scored.sort(key=lambda t: -t[0])
    return [r for s, r in scored if s > 0][:top_k] or [r for _, r in scored[:top_k]]


def _vector_rank(query, records, top_k):
    """Rank the (already metadata-filtered) records by cosine to the query.

    Embeds the small filtered set on the fly — avoids a separate index step and
    keeps results consistent with the live records. Raises on any DB/embed error
    so search() can fall back to keyword ranking."""
    from . import embed
    import numpy as np
    if not records:
        return []
    qv = np.array(embed.embed_one(query), dtype=float)
    mv = np.array(embed.embed([r.get("text", "") for r in records]), dtype=float)
    sims = mv @ qv  # vectors are L2-normalised → cosine
    order = np.argsort(-sims)
    return [records[i] for i in order[:top_k]]


def search(query, types=None, tags=None, confidence_min=None, status=None,
           include_superseded=False, top_k=10):
    """Retrieve typed records: metadata-filter (always) → semantic rank (DB up) or
    keyword rank (fallback). Returns a list of record dicts (best first)."""
    records = memory.load_records(types)
    records = _filter(records, tags=tags, confidence_min=confidence_min,
                      status=status, include_superseded=include_superseded)
    if not query:
        return records[:top_k]
    if db_available():
        try:
            return _vector_rank(query, records, top_k)
        except Exception:
            pass  # fall back to keyword
    return _keyword_rank(query, records, top_k)


def index_all(types=None):
    """Embed every typed record into Qdrant (one collection per type) for
    persistent semantic search. Requires the vector DB + clients; raises with a
    clear message otherwise (search() still works without it)."""
    from . import litdb, embed
    from qdrant_client.models import Distance, VectorParams, PointStruct
    mc, qc = litdb._clients()
    recs = memory.load_records(types)
    by_type = {}
    for r in recs:
        by_type.setdefault(r["type"], []).append(r)
    total = 0
    for rtype, rs in by_type.items():
        coll = f"kb_{rtype}"
        have = [c.name for c in qc.get_collections().collections]
        if coll not in have:
            qc.create_collection(coll, vectors_config=VectorParams(
                size=embed.dim(), distance=Distance.COSINE))
        vecs = embed.embed([r.get("text", "") for r in rs])
        pts = [PointStruct(id=litdb._pid(r["id"]), vector=v,
                           payload={"id": r["id"], "tags": r.get("tags") or [],
                                    "status": r.get("status"),
                                    "confidence": r.get("confidence")})
               for r, v in zip(rs, vecs)]
        qc.upsert(coll, points=pts)
        total += len(pts)
    return total
