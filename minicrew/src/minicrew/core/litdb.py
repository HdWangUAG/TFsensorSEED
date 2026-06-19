"""Literature index: MongoDB (full text + metadata) + Qdrant (vectors).

This INDEXES the distilled .md notes (litstore = source-of-truth) for semantic
retrieval; it never replaces them. `index_all()` is idempotent — wipe the DB and
re-run any time. Clients are imported lazily so the rest of minicrew works
without pymongo/qdrant installed or the containers running.

    cd minicrew && docker compose up -d
    minicrew index
    minicrew search "aromatic A-ring recognition of estradiol"
"""
from __future__ import annotations

import hashlib
import os

from . import config, embed, litstore

_VECTOR_SIZE = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}
_META = ("title", "authors", "year", "doi", "tags", "trust", "relevance")


def _clients():
    from pymongo import MongoClient
    from qdrant_client import QdrantClient
    mc = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=3000)
    qc = QdrantClient(url=config.QDRANT_URL, timeout=15)
    return mc, qc


def _pid(name):
    return int(hashlib.sha1(name.encode()).hexdigest()[:15], 16)


def _ensure_collection(qc, dim):
    from qdrant_client.models import Distance, VectorParams
    have = [c.name for c in qc.get_collections().collections]
    if config.QDRANT_COLLECTION not in have:
        qc.create_collection(
            config.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE))


def status():
    """(ok, message) — is the DB backend reachable?"""
    try:
        mc, qc = _clients()
        mc.admin.command("ping")
        qc.get_collections()
        return True, f"mongo={config.MONGO_URI}  qdrant={config.QDRANT_URL}"
    except Exception as exc:  # noqa: BLE001 — surface any client/conn error
        return False, str(exc)[:200]


def index_all():
    """(Re)index every literature note from files into Mongo + Qdrant."""
    from qdrant_client.models import PointStruct
    notes = litstore.list_notes()
    if not notes:
        return 0
    mc, qc = _clients()
    dim = _VECTOR_SIZE.get(config.EMBED_MODEL, 1536)
    _ensure_collection(qc, dim)
    col = mc[config.MONGO_DB]["literature"]
    bodies = [litstore.read(n["path"]) for n in notes]
    vecs = embed.embed(bodies)
    points = []
    for n, body, vec in zip(notes, bodies, vecs):
        doc = {"_id": n["name"], "body": body,
               "path": os.path.relpath(n["path"], config.REPO_ROOT)}
        doc.update({k: n.get(k) for k in _META if n.get(k) is not None})
        col.replace_one({"_id": n["name"]}, doc, upsert=True)
        points.append(PointStruct(
            id=_pid(n["name"]), vector=vec,
            payload={"name": n["name"], "title": n.get("title", n["name"]),
                     "tags": n.get("tags") or [], "trust": n.get("trust"),
                     "year": n.get("year")}))
    qc.upsert(config.QDRANT_COLLECTION, points=points)
    return len(points)


def search(query, k=5, tags=None):
    """Semantic search → [{score, name, title, tags, trust, body}] (best first)."""
    from qdrant_client.models import FieldCondition, Filter, MatchAny
    mc, qc = _clients()
    qvec = embed.embed_one(query)
    flt = None
    if tags:
        flt = Filter(must=[FieldCondition(key="tags", match=MatchAny(any=list(tags)))])
    hits = qc.query_points(config.QDRANT_COLLECTION, query=qvec,
                           limit=k, query_filter=flt).points
    col = mc[config.MONGO_DB]["literature"]
    out = []
    for h in hits:
        name = (h.payload or {}).get("name")
        doc = col.find_one({"_id": name}) or {}
        out.append({"score": h.score, "name": name,
                    "title": (h.payload or {}).get("title", name),
                    "tags": (h.payload or {}).get("tags"),
                    "trust": doc.get("trust"), "body": doc.get("body", "")})
    return out
