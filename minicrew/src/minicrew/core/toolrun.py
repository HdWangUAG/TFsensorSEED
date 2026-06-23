"""Tool-Request protocol — let reasoning agents *act* inside a crew, cheaply.

An agent (any provider, including `claude_cli`) requests a skill by emitting a
fenced block in its reply:

    ```tool_request
    skill: analyze_structure
    args:
      pdb_path: data/AcrR_STR_001.pdb
      ligand_resname: STR
    reason: inspect whether the 3-keto is H-bonded
    ```

The crew runtime parses it, enforces the crew/role tool allow-list, runs the
skill **deterministically** via `skills.call` (no extra LLM call to execute —
the request is already structured, so this works for non-tool-calling providers
like claude_cli and costs nothing), then:
  - dumps the full SkillResult to `artifacts/<run_id>/result.json`,
  - writes a computational-evidence stub (`evidence.md`) so the run is
    recallable later (the Tool-Run→Evidence bridge),
  - returns only a COMPACT digest to fold into the transcript (hygiene: big
    JSON / stdout stays in the artifact, never in the prompt).

This is the deterministic path. Native OpenAI function-calling (toolcall.run) is
reserved for an autonomous Tool-Runner and is gated by provider in crew.py.
"""
from __future__ import annotations

import json
import os
import re
import threading

import yaml

from . import config, skills

ARTIFACTS_DIR = os.path.join(config.MINICREW_DIR, "artifacts")
_FENCE = re.compile(r"```tool_request\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)

# heavy (GPU / long) skills are serialized (a GPU can't run two folds at once)
# and capped per crew run by a budget.
HEAVY_RUNTIME_S = 600
_HEAVY_LOCK = threading.Lock()
DEFAULT_HEAVY_BUDGET = 4


def _is_heavy(name):
    s = skills.SKILLS.get(name)
    return bool(s and (s.requires or {}).get("max_runtime_seconds", 0) >= HEAVY_RUNTIME_S)


def parse_requests(text):
    """Extract structured tool requests from an agent's reply."""
    reqs = []
    for m in _FENCE.finditer(text or ""):
        try:
            d = yaml.safe_load(m.group(1))
        except Exception:
            continue
        if isinstance(d, dict) and d.get("skill"):
            reqs.append({"skill": str(d["skill"]).strip(),
                         "args": d.get("args") or {},
                         "reason": d.get("reason", "")})
    return reqs


def _write_evidence(run_dir, res, req, requested_by):
    """Minimal computational-evidence record (P2 will formalize the typed schema)."""
    prov = res.get("provenance") or {}
    fm = [
        "---", "type: evidence", "source_type: computational_tool",
        "status: candidate  # tool output — NOT recalled by default until promoted to active",
        f"skill: {res['skill']}", f"ok: {res['ok']}",
        f"run_id: {prov.get('run_id', '')}", f"requested_by: {requested_by}",
        f"runtime_seconds: {prov.get('runtime_seconds', '')}",
        "trust: MEDIUM  # binding-ΔΔG/pose tools are coarse — see COMPUTATIONAL_BOUNDARY.md",
        "---", "",
        f"## Tool run: {res['skill']}",
        f"- reason: {req.get('reason', '')}",
        f"- args: {json.dumps(req.get('args', {}))}",
        f"- result: {json.dumps(res.get('result', {}), default=str)[:800]}",
    ]
    for a in res.get("artifacts", []):
        fm.append(f"- artifact: {a.get('type')} {a.get('uri')}")
    if res.get("warnings"):
        fm.append("- warnings: " + "; ".join(res["warnings"]))
    path = os.path.join(run_dir, "evidence.md")
    open(path, "w").write("\n".join(fm))
    return path


def _deny(name, msg, on_event):
    comp = f"[skill {name} | DENIED] {msg}"
    if on_event:
        on_event({"type": "tool", "skill": name, "ok": False, "denied": True, "compact": comp})
    return {"skill": name, "ok": False, "compact": comp, "result_path": None,
            "evidence_path": None, "denied": True, "artifacts": []}


def execute(requests, allowed_tools, requested_by="agent", on_event=None, budget=None):
    """Run each request with STRICT gating: well-formedness → allow-list → heavy
    budget → (args-validation + preflight + path-safety happen inside skills.call).
    Heavy/GPU skills are serialized via _HEAVY_LOCK. `budget` is a mutable dict
    {'heavy_remaining': N} tracked across the whole crew run."""
    out = []
    for req in requests:
        name, args = req.get("skill"), req.get("args", {})
        if not isinstance(name, str) or not name or not isinstance(args, dict):
            out.append(_deny(str(name), "malformed request (need skill:str + args:dict)", on_event))
            continue
        if allowed_tools is not None and name not in allowed_tools:
            out.append(_deny(name, f"not in this crew's allow-list {sorted(allowed_tools)}", on_event))
            continue
        if name not in skills.SKILLS:
            out.append(_deny(name, "unknown skill", on_event))
            continue
        heavy = _is_heavy(name)
        if heavy and budget is not None and budget.get("heavy_remaining", 0) <= 0:
            out.append(_deny(name, "heavy-tool budget exhausted for this run", on_event))
            continue
        # args validation + preflight + path safety are enforced inside skills.call;
        # heavy/GPU skills are serialized so a GPU isn't oversubscribed.
        if heavy:
            if budget is not None:
                budget["heavy_remaining"] = budget.get("heavy_remaining", 0) - 1
            with _HEAVY_LOCK:
                res = skills.call(name, **args)
        else:
            res = skills.call(name, **args)
        rid = (res.get("provenance") or {}).get("run_id") or skills.run_id()
        run_dir = os.path.join(ARTIFACTS_DIR, rid)   # per tool-run; never overwrites
        os.makedirs(run_dir, exist_ok=True)
        rp = os.path.join(run_dir, "result.json")
        json.dump(res, open(rp, "w"), indent=2, default=str)
        ev = _write_evidence(run_dir, res, req, requested_by)
        comp = skills.compact(res)                   # digest only — full result in rp
        out.append({"skill": name, "ok": res["ok"], "compact": comp,
                    "result_path": rp, "evidence_path": ev, "denied": False,
                    "artifacts": res.get("artifacts", [])})
        if on_event:
            on_event({"type": "tool", "skill": name, "ok": res["ok"],
                      "compact": comp, "result_path": rp})
    return out


def _arg_spec(skill_obj):
    """Render a skill's parameters so agents use the EXACT arg names (no guessing)."""
    params = skill_obj.parameters or {}
    props = params.get("properties", {})
    required = set(params.get("required", []))
    if not props:
        return "    (no args)"
    out = []
    for name, p in props.items():
        tag = "required" if name in required else "optional"
        desc = p.get("description", "")
        out.append(f"    {name} ({p.get('type', 'string')}, {tag})"
                   + (f" — {desc}" if desc else ""))
    return "\n".join(out)


def tools_block(allowed_tools):
    """Prompt section telling agents which skills exist + their EXACT args + how
    to request one. Surfacing the real arg names is essential — otherwise agents
    guess (`pdb`/`ligand`) and the call is rejected by validation."""
    if not allowed_tools:
        return ""
    lines = ["## Tools you can run (request, don't guess the answer)",
             "To run a skill, emit a fenced block — it executes and the result is "
             "added to the discussion. Use the EXACT arg names listed below:", "",
             "```tool_request", "skill: <name>", "args:", "  <arg_name>: <value>",
             "reason: <why you need it>", "```", "",
             "Available skills (with their args):"]
    for n in allowed_tools:
        s = skills.SKILLS.get(n)
        if s:
            lines.append(f"\n- **{n}**: {s.description}")
            lines.append(_arg_spec(s))
    lines.append("\nRequest a tool only when a real computation would change your "
                 "answer; results are computational evidence (coarse — weigh per "
                 "COMPUTATIONAL_BOUNDARY.md), not ground truth.")
    return "\n".join(lines)


# Providers whose models support native OpenAI function-calling (toolcall.run).
NATIVE_TOOLCALL_PROVIDERS = {"openai"}


def assert_tool_routing(role, spec):
    """Provider-aware guard: a role may only use NATIVE tool-calling if its
    provider supports it. claude_cli etc. must use the (delegated) Tool-Request
    protocol instead. Raises ValueError on a misconfigured role."""
    if role.get("use_native_tools") and spec["provider"] not in NATIVE_TOOLCALL_PROVIDERS:
        raise ValueError(
            f"role {role.get('name')!r} sets use_native_tools but provider "
            f"{spec['provider']!r} has no native tool-calling — drop use_native_tools "
            f"(it will use the Tool-Request protocol) or switch to an openai model.")
