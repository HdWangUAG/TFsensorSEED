"""Typed project knowledge with provenance + trust tiers.

Knowledge is grounding material the whole crew sees, labelled by how reliable its
source is so agents weigh wet-lab results over model priors. Categories
(`config.KNOWLEDGE_SOURCES`) map to directories; each file becomes a block tagged
with its category's trust tier (`config.KNOWLEDGE_TRUST`) and its file path
(provenance). `pitfalls` also pulls the repo's curated `docs/agent_memory/`.

A crew opts in via `knowledge: [pitfalls, computational, ...]` in its YAML.
README.md files are skipped (they're templates, not knowledge).
"""
from __future__ import annotations

import glob
import os

from . import config
from .context import _read  # truncating reader, shared with context files


def _files(category):
    out = []
    for src in config.KNOWLEDGE_SOURCES.get(category, []):
        src = os.path.expanduser(src)
        if os.path.isdir(src):
            for ext in ("*.md", "*.txt"):
                out += sorted(glob.glob(os.path.join(src, ext)))
        elif os.path.isfile(src):
            out.append(src)
        else:
            out += sorted(glob.glob(src))
    # drop templates (README.md, _*.md); de-dup, keep order
    seen, uniq = set(), []
    for p in out:
        base = os.path.basename(p)
        if base.lower() == "readme.md" or base.startswith("_"):
            continue
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _literature_retrieved(query):
    """Top-k (cosine) literature relevant to `query`, or None to fall back to
    files (DB down / no key / no client). Drops hits below LIT_MIN_SCORE."""
    try:
        from . import litdb
        ok, _ = litdb.status()
        if not ok:
            return None
        hits = [h for h in litdb.search(query, k=config.LIT_TOPK)
                if h["score"] >= config.LIT_MIN_SCORE]
    except Exception:
        return None
    trust = config.KNOWLEDGE_TRUST.get("literature", "unspecified")
    if not hits:
        return f"### [literature]  trust: {trust}\n(no note passed the relevance threshold for this task)"
    blocks = [f"### [literature]  trust: {trust}  "
              f"(top-{len(hits)} by semantic relevance to the task)"]
    for h in hits:
        blocks.append(f"[source: knowledge/literature/{h['name']} · "
                      f"cosine {h['score']:.2f}]\n{h['body']}")
    return "\n\n".join(blocks)


# typed-record categories that GROW with use → retrieve by relevance, not dump.
# (pitfalls stays whole-file so the curated docs/agent_memory/ is never dropped.)
_TYPED_CAT = {"decisions": "decision", "claims": "claim", "evidence": "evidence"}


def _typed_retrieved(cat, query):
    """Top-k relevant typed records for a category (status-filtered), or None to
    fall back to whole-file injection (no records yet)."""
    from . import kdb
    rtype = _TYPED_CAT[cat]
    recs = kdb.search(query, types=[rtype], top_k=config.LIT_TOPK)
    if not recs:
        return None
    trust = config.KNOWLEDGE_TRUST.get(cat, "unspecified")
    blocks = [f"### [{cat}]  trust: {trust}  "
              f"(top-{len(recs)} relevant records; superseded hidden)"]
    for r in recs:
        blocks.append(f"[record {r['id']} · status={r.get('status')} · "
                      f"conf={r.get('confidence')}]\n{r.get('text', '')}")
    return "\n\n".join(blocks)


def build(categories, query=None):
    """Return a formatted, trust-labelled knowledge block (or "" if none).

    When `query` is given, growing categories are RETRIEVED by relevance instead
    of dumped: `literature` semantically (if the DB is up), and the typed-record
    categories (decisions/claims/evidence) via kdb (status-filtered). Curated
    categories (pitfalls/computational/experimental/engineering) stay whole-file.
    """
    if not categories:
        return ""
    sections = []
    for cat in categories:
        if cat == "literature" and query:
            sec = _literature_retrieved(query)
            if sec is not None:
                sections.append(sec)
                continue  # else fall through to whole-files injection
        if cat in _TYPED_CAT and query:
            sec = _typed_retrieved(cat, query)
            if sec is not None:
                sections.append(sec)
                continue
        files = _files(cat)
        if not files:
            continue
        trust = config.KNOWLEDGE_TRUST.get(cat, "unspecified")
        blocks = [f"### [{cat}]  trust: {trust}"]
        for p in files:
            rel = os.path.relpath(p, config.REPO_ROOT)
            blocks.append(f"[source: {rel}]\n{_read(p)}")
        sections.append("\n\n".join(blocks))
    return "\n\n".join(sections)
