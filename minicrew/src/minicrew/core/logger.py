"""Persist a run two ways: a human transcript and a machine record.

The transcript is your microscope — for every agent it records BOTH the reply
and (collapsed) the exact prompt that agent saw, so you can always explain why
it said what it said. The JSON record carries the same data plus an input hash,
for later run-to-run comparison.

    results/minicrew/conversations/<ts>_<crew>.md
    results/minicrew/runs/<ts>_<crew>.json
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os

from . import config


def _hash(text):
    return hashlib.sha256((text or "").encode()).hexdigest()[:12]


def save_run(crew, topology, transcript, out_path=None):
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{ts}_{crew['name']}"
    conv_dir = config.CONV_DIR
    runs_dir = config.RUNS_DIR
    os.makedirs(conv_dir, exist_ok=True)
    os.makedirs(runs_dir, exist_ok=True)

    task = crew.get("task", crew.get("description", ""))
    md = [f"# Run: {crew['name']}", "",
          f"- topology: **{topology}**", f"- time: {ts}",
          f"- task: {task}", ""]
    for t in transcript:
        tag = " — synthesis" if t["kind"] == "moderator" else ""
        md.append(f"## {t['role']} [{t['alias']}:{t['model']}]{tag}\n")
        md.append(t["content"])
        md.append("\n<details><summary>prompt this agent saw</summary>\n")
        md.append(f"```\n{t['prompt_seen']}\n```\n</details>\n")
    md_path = out_path or os.path.join(conv_dir, f"{stem}.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))

    record = {
        "run_id": stem,
        "crew": crew["name"],
        "topology": topology,
        "timestamp": ts,
        "task": task,
        "outputs": [
            {"agent": t["role"], "alias": t["alias"], "model": t["model"],
             "kind": t["kind"], "ok": t["ok"],
             "prompt_seen": t["prompt_seen"], "reply": t["content"],
             "prompt_hash": _hash(t["prompt_seen"])}
            for t in transcript
        ],
    }
    with open(os.path.join(runs_dir, f"{stem}.json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, ensure_ascii=False)
    return record
