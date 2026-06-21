"""Assemble the shared briefing context handed to every agent.

Sources, in order:
  1. the crew's declared `context_files` (globs, relative to repo root)
  2. extra files passed on the CLI with --file (repeatable)

Each file is truncated to keep the briefing within a sane token budget; the head
of a long file is usually the summary/plan, which is what we want.
"""
from __future__ import annotations

import glob
import os

from . import config

MAX_CHARS_PER_FILE = int(config.get("MINICREW_MAX_CHARS_PER_FILE", "6000"))


def _read(path, max_chars=MAX_CHARS_PER_FILE):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        return f"[could not read {path}: {exc}]"
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n…[truncated, {len(text)} chars total]"
    return text


def _resolve(patterns):
    """Expand globs (relative to repo root or absolute) into existing files."""
    out = []
    for pat in patterns or []:
        p = os.path.expanduser(pat)
        if not os.path.isabs(p):
            p = os.path.join(config.REPO_ROOT, p)
        matches = sorted(glob.glob(p))
        out.extend(matches or [])
    # de-dup, keep order
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def build(context_files=None, extra_files=None):
    """Return a single formatted context string from declared + CLI files."""
    blocks = []
    for path in _resolve(context_files) + list(extra_files or []):
        rel = os.path.relpath(path, config.REPO_ROOT)
        blocks.append(f"### File: {rel}\n```\n{_read(path)}\n```")
    if not blocks:
        return "(no context files provided)"
    return "\n\n".join(blocks)
