"""CRUD for crew definitions (agent teams) — the configs/*.yaml files.

Lets the app assemble agents from the registry into a new team for a new topic,
so MiniCrew is a general platform: build agents (agents.py) → assemble a crew
here → run it in the Discussion room. crew.py still loads/runs these files.
"""
from __future__ import annotations

import glob
import os

import yaml

from . import config


def _path(name):
    fname = name if name.endswith((".yaml", ".yml")) else name + ".yaml"
    return os.path.join(config.CONFIGS_DIR, os.path.basename(fname))


def list_crews():
    out = {}
    for p in sorted(glob.glob(os.path.join(config.CONFIGS_DIR, "*.y*ml"))):
        out[os.path.splitext(os.path.basename(p))[0]] = p
    return out


def get(name):
    with open(_path(name), encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def delete(name):
    p = _path(name)
    if os.path.isfile(p):
        os.remove(p)
        return True
    return False


def build_spec(name, project, task, topology, rounds, knowledge,
               context_files, evidence_files, reviewers, moderator):
    """reviewers: [{name, model, persona_file}]; moderator: same or None."""
    spec = {"name": name, "project": project, "topology": topology,
            "task": task.strip()}
    if topology == "round_robin":
        spec["rounds"] = int(rounds)
    if context_files:
        spec["context_files"] = context_files
    if evidence_files:
        spec["evidence_files"] = evidence_files
    if knowledge:
        spec["knowledge"] = knowledge
    spec["roles"] = reviewers
    if moderator:
        spec["synthesizer"] = moderator
    return spec


def save(name, spec):
    os.makedirs(config.CONFIGS_DIR, exist_ok=True)
    p = _path(name)
    with open(p, "w", encoding="utf-8") as fh:
        yaml.safe_dump(spec, fh, sort_keys=False, allow_unicode=True, width=88)
    return p
