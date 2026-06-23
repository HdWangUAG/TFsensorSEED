"""Typed scientific memory — claims, evidence, decisions, pitfalls as records.

A *record* is a small markdown file with YAML frontmatter (git-versioned,
human-readable — the same on-disk shape crews already read) PLUS the structure a
co-scientist needs: a stable content-hash ID, tags, and — crucially — **`status`
and `confidence` as DISTINCT fields** (a claim can be `status: mixed` yet
`confidence: high`: we're confident the evidence is mixed). Evidence carries a
controlled **`relation`** vocab; decisions carry **supersession** so a reversal
(e.g. BO→wet-lab) is recorded, not left as two contradictory notes.

Records live under knowledge/<type>s/ so retrieval (kdb) and the existing
knowledge layer both see them. This module is pure-stdlib (+pyyaml).
"""
from __future__ import annotations

import datetime
import hashlib
import os
import re

import yaml

from . import config

TYPE_DIR = {"claim": "claims", "evidence": "evidence",
            "decision": "decisions", "pitfall": "pitfalls"}
STATUS = {"open", "supported", "refuted", "mixed", "superseded",
          "active", "rejected", "expired"}
CONFIDENCE = {"low", "medium", "high"}
CONF_RANK = {"low": 0, "medium": 1, "high": 2}
RELATION = {"supports", "weakly_supports", "refutes", "mixed",
            "insufficient", "not_relevant"}
_DEFAULT_STATUS = {"claim": "open", "decision": "active",
                   "pitfall": "active", "evidence": "active"}
# frontmatter keys we persist (everything filterable lives here)
_FM_KEYS = ("id", "type", "tags", "status", "confidence", "created", "source_run",
            "relation", "claim_ids", "evidence_ids", "supersedes", "superseded_by",
            "owner", "next_step", "severity", "epistemic_status", "source_type", "skill")

# small project vocab → deterministic auto-tags (so records are filterable)
_TAG_VOCAB = ["testosterone", "progesterone", "cortisol", "estradiol", "selectivity",
              "specificity", "pose", "orientation", "flex-ddg", "ddg", "boltz", "gate",
              "epistasis", "dose-response", "amplitude", "allostery", "pocket",
              "pymol", "surrogate", "bayesian", "wet-lab", "retrodiction", "ec50"]


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def _norm(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def record_id(rtype, text):
    """Stable content-hash id, e.g. 'dec_1a2b3c4d' (same text → same id = dedup)."""
    h = hashlib.sha1(f"{rtype}|{_norm(text)}".encode()).hexdigest()[:8]
    return f"{rtype[:3]}_{h}"


def auto_tags(text):
    t = _norm(text)
    return [v for v in _TAG_VOCAB if v in t]


def make_record(rtype, text, *, tags=None, confidence="medium", status=None,
                source_run=None, relation=None, **extra):
    if rtype not in TYPE_DIR:
        raise ValueError(f"unknown record type {rtype!r} (use {sorted(TYPE_DIR)})")
    confidence = confidence if confidence in CONFIDENCE else "medium"
    status = status if status in STATUS else _DEFAULT_STATUS[rtype]
    if rtype == "evidence" and relation not in RELATION:
        relation = relation if relation in RELATION else "supports"
    rec = {"id": record_id(rtype, text), "type": rtype, "text": text.strip(),
           "tags": sorted(set((tags or []) + auto_tags(text))),
           "status": status, "confidence": confidence, "created": _now(),
           "source_run": source_run}
    if rtype == "evidence":
        rec["relation"] = relation
    rec.update({k: v for k, v in extra.items() if v is not None})
    return rec


def to_markdown(rec):
    fm = {k: rec[k] for k in _FM_KEYS if k in rec and rec[k] is not None}
    body = rec.get("text", "")
    # render structured sub-fields into the body for human reading
    for label, key in (("owner", "owner"), ("next step", "next_step"),
                       ("severity", "severity"), ("relation", "relation")):
        if rec.get(key):
            body += f"\n\n**{label}:** {rec[key]}"
    for label, key in (("detection", "detection"), ("mitigation", "mitigation"),
                       ("trigger context", "trigger_context")):
        v = rec.get(key)
        if v:
            items = v if isinstance(v, list) else [v]
            body += f"\n\n**{label}:**\n" + "\n".join(f"- {x}" for x in items)
    return f"---\n{yaml.safe_dump(fm, sort_keys=False).strip()}\n---\n\n{body.strip()}\n"


def parse(path):
    """Read a record file → dict (frontmatter + `text` body). None if not a record."""
    try:
        txt = open(path, encoding="utf-8").read()
    except OSError:
        return None
    if not txt.startswith("---"):
        return None
    end = txt.find("\n---", 3)
    if end == -1:
        return None
    try:
        fm = yaml.safe_load(txt[3:end]) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict) or "type" not in fm:
        return None
    body = txt[end + 4:].strip()
    fm["text"] = fm.get("text") or body.split("\n\n")[0].strip()
    fm["_body"] = body
    fm["_path"] = path
    return fm


def dir_for(rtype):
    return os.path.join(config.KNOWLEDGE_DIR, TYPE_DIR[rtype])


def write_record(rec):
    d = dir_for(rec["type"])
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{rec['id']}.md")
    open(path, "w", encoding="utf-8").write(to_markdown(rec))
    return path


def load_records(types=None):
    """All typed records on disk (optionally filtered to `types`)."""
    import glob
    out = []
    for rtype, sub in TYPE_DIR.items():
        if types and rtype not in types:
            continue
        for p in sorted(glob.glob(os.path.join(config.KNOWLEDGE_DIR, sub, "*.md"))):
            base = os.path.basename(p)
            if base.lower() == "readme.md" or base.startswith("_"):
                continue
            rec = parse(p)
            if rec and rec.get("type") == rtype:
                out.append(rec)
    return out


def get(record_id_):
    for r in load_records():
        if r.get("id") == record_id_:
            return r
    return None


def supersede(old_id, new_id=None, note=None):
    """Mark a decision superseded (link → new_id). Returns the updated record path."""
    rec = get(old_id)
    if rec is None:
        raise KeyError(f"record {old_id!r} not found")
    rec["status"] = "superseded"
    if new_id:
        rec["superseded_by"] = new_id
    if note:
        rec["_body"] = (rec.get("_body", "") + f"\n\n**superseded:** {note}")
        rec["text"] = rec.get("text", "")
    # rewrite from parsed dict (drop private keys)
    clean = {k: v for k, v in rec.items() if not k.startswith("_")}
    clean.setdefault("text", rec.get("text", ""))
    path = os.path.join(dir_for(rec["type"]), f"{rec['id']}.md")
    open(path, "w", encoding="utf-8").write(to_markdown(clean))
    return path
