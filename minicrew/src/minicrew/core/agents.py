"""Agent registry — persona & tool agents as editable files.

An agent is a Markdown file:
  - knowledge agents (viewpoints)  → prompts/personas/<file>.md
  - tool agents (capabilities)     → prompts/tools/<file>.md
Optional YAML frontmatter carries name / model / description; the body is the
system prompt. Files without frontmatter still work (name from the filename, no
default model) so hand-written personas keep loading. The app does CRUD here;
crews reference the same files via `persona_file`.
"""
from __future__ import annotations

import glob
import os

import yaml

from . import config

DIRS = {
    "persona": os.path.join(config.PROMPTS_DIR, "personas"),
    "tool": os.path.join(config.PROMPTS_DIR, "tools"),
}


def split_frontmatter(text):
    """Return (meta_dict, body). meta is {} when there's no frontmatter."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            try:
                meta = yaml.safe_load(text[3:end]) or {}
            except yaml.YAMLError:
                meta = {}
            if isinstance(meta, dict):
                return meta, text[end + 4:].lstrip("\n")
    return {}, text


def _record(kind, path):
    base = os.path.basename(path)
    with open(path, encoding="utf-8") as fh:
        meta, body = split_frontmatter(fh.read())
    return {
        "kind": kind, "file": base, "path": path,
        "name": meta.get("name") or base[:-3].replace("_", " ").title(),
        "model": meta.get("model"),
        "description": meta.get("description", ""),
        "capabilities": meta.get("capabilities", ""),
        "limitations": meta.get("limitations", ""),
        "body": body.strip(),
    }


def list_agents(kind=None):
    kinds = [kind] if kind else list(DIRS)
    out = []
    for k in kinds:
        d = DIRS[k]
        if not os.path.isdir(d):
            continue
        for p in sorted(glob.glob(os.path.join(d, "*.md"))):
            base = os.path.basename(p)
            if base.lower() == "readme.md" or base.startswith("_"):
                continue
            out.append(_record(k, p))
    return out


def get(kind, file):
    return _record(kind, os.path.join(DIRS[kind], file))


def save(kind, file, name, body, model=None, description=""):
    """Create or overwrite an agent file (with frontmatter). Returns its path."""
    os.makedirs(DIRS[kind], exist_ok=True)
    base = os.path.basename(file.strip()) or "agent.md"
    if not base.endswith(".md"):
        base += ".md"
    fm = {"name": name, "type": kind}
    if model:
        fm["model"] = model
    if description:
        fm["description"] = description
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    content = f"---\n{front}\n---\n\n{body.strip()}\n"
    path = os.path.join(DIRS[kind], base)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def delete(kind, file):
    path = os.path.join(DIRS[kind], os.path.basename(file))
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False
