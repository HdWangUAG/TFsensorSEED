"""Save runs so you can trace back and diagnose.

For a learning project the transcript is your microscope. We deliberately
record `prompt_seen` for every agent — the thing the original plan treated as
incidental — because seeing what an agent saw is how you explain what it said.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from .crew import RunContext


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def save_run(ctx: RunContext, crew_name: str, topology: str, out_root: Path) -> dict:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{ts}_{crew_name}"
    for sub in ("conversations", "runs", "tasks"):
        (out_root / sub).mkdir(parents=True, exist_ok=True)

    # --- markdown transcript (for humans) ---
    md = [f"# Run: {crew_name}", f"- topology: **{topology}**",
          f"- time: {ts}", f"- input hash: `{_hash(ctx.user_input)}`", ""]
    for o in ctx.outputs:
        md.append(f"## {o.agent}\n")
        md.append(o.reply)
        md.append("\n<details><summary>prompt this agent saw</summary>\n")
        md.append(f"```\n{o.prompt_seen}\n```\n</details>\n")
    (out_root / "conversations" / f"{stem}.md").write_text("\n".join(md))

    # --- json record (for machines / later comparison) ---
    record = {
        "run_id": stem,
        "crew": crew_name,
        "topology": topology,
        "timestamp": ts,
        "input_hash": _hash(ctx.user_input),
        "outputs": [
            {"agent": o.agent, "prompt_seen": o.prompt_seen, "reply": o.reply}
            for o in ctx.outputs
        ],
    }
    (out_root / "runs" / f"{stem}.json").write_text(json.dumps(record, indent=2))
    return record
