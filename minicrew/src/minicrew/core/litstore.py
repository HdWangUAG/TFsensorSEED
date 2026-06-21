"""Literature store — the seam between the app and where notes live.

v1 backend = files: distilled `.md` notes in knowledge/literature/ (git-versioned,
human-readable, the source-of-truth). A future MongoQdrantStore will implement the
same `save / list_notes / read` interface and *index* these files (text → Mongo,
vectors → Qdrant) rather than replace them, so the GUI/crew never change.
"""
from __future__ import annotations

import glob
import os

import yaml

from . import config

LIT_DIR = os.path.join(config.KNOWLEDGE_DIR, "literature")
_META_KEYS = ("title", "authors", "year", "doi", "tags", "trust", "relevance")


def _read_meta(path):
    try:
        with open(path, encoding="utf-8") as fh:
            txt = fh.read()
    except OSError:
        return {}
    if txt.startswith("---"):
        end = txt.find("\n---", 3)
        if end != -1:
            try:
                fm = yaml.safe_load(txt[3:end])
                if isinstance(fm, dict):
                    return {k: fm.get(k) for k in _META_KEYS if k in fm}
            except yaml.YAMLError:
                pass
    return {}


def save(filename, content):
    """Write a note; returns its path. Templates (README/_*) are not overwritten."""
    os.makedirs(LIT_DIR, exist_ok=True)
    base = os.path.basename(filename.strip()) or "untitled.md"
    if not base.endswith(".md"):
        base += ".md"
    if base.lower() == "readme.md" or base.startswith("_"):
        base = "note_" + base.lstrip("_")
    path = os.path.join(LIT_DIR, base)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def list_notes():
    """Return [{path, name, title, tags, ...}] for real notes (not templates)."""
    out = []
    for p in sorted(glob.glob(os.path.join(LIT_DIR, "*.md"))):
        base = os.path.basename(p)
        if base.lower() == "readme.md" or base.startswith("_"):
            continue
        out.append({"path": p, "name": base, **_read_meta(p)})
    return out


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()
