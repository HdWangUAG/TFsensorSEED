"""Tool-calling loop — let a model call real tools and reason on the results.

Uses OpenAI-style function-calling (gpt-5.x / gpt-4o, also the ELM proxy). The
model may request tools from the registry; we execute them and feed the results
back until it gives a final answer. Returns (answer, trace) where trace lists
every tool call + its real result — the receipts.
"""
from __future__ import annotations

import json

import requests

from . import config, tools
from .llm import LLMError, _is_newer_openai, _raise_for_status


def run(system, user, model="openai", tool_names=None, max_rounds=5):
    spec = config.resolve_model(model)
    if spec["provider"] != "openai":
        raise LLMError("tool-calling needs an OpenAI-compatible model "
                       "(openai / edinburgh) — set the tool model accordingly")
    if not spec.get("api_key"):
        raise LLMError("no API key for the tool model")
    url = spec["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {spec['api_key']}",
               "Content-Type": "application/json"}
    schemas = tools.openai_schemas(tool_names)
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
    trace = []

    for _ in range(max_rounds):
        body = {"model": spec["model"], "messages": messages,
                "tools": schemas, "tool_choice": "auto"}
        if _is_newer_openai(spec["model"]):
            body["max_completion_tokens"] = 8000
        else:
            body["max_tokens"] = 2000
            body["temperature"] = 0.2
        r = requests.post(url, headers=headers, json=body, timeout=config.HTTP_TIMEOUT)
        _raise_for_status(r)
        msg = r.json()["choices"][0]["message"]
        messages.append(msg)
        calls = msg.get("tool_calls")
        if not calls:
            return (msg.get("content") or "").strip(), trace
        for tc in calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
                result = tools.REGISTRY[name]["fn"](**args)
            except Exception as exc:                       # tool error → tell the model
                result = {"error": str(exc)}
                args = locals().get("args", {})
            trace.append({"tool": name, "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "content": json.dumps(result)})
    return "(stopped: too many tool rounds)", trace
