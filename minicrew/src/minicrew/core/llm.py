"""Provider-agnostic LLM calls over plain HTTP (requests only).

Three provider shapes cover everything we need:
  - anthropic : POST /v1/messages          (Claude)
  - openai    : POST /v1/chat/completions  (OpenAI *and* Edinburgh ELM proxy)
  - gemini    : POST /v1beta/models/<m>:generateContent

Each call takes a resolved model spec (see config.resolve_model) plus a system
prompt and a single user message, and returns plain text. Errors are wrapped in
LLMError so the orchestrator can show a readable per-agent failure instead of a
traceback.
"""
from __future__ import annotations

import base64
import os
import shutil
import subprocess

import requests

from . import config


class LLMError(RuntimeError):
    pass


def call(spec, system, prompt, max_tokens=None, temperature=None):
    """Dispatch to the right provider and return the assistant's text."""
    provider = spec["provider"]
    max_tokens = max_tokens or config.DEFAULT_MAX_TOKENS
    temperature = config.DEFAULT_TEMPERATURE if temperature is None else temperature

    # claude_cli uses the local Claude Code subscription — no API key needed.
    if provider == "claude_cli":
        return _claude_cli(spec, system, prompt)

    if not spec.get("api_key"):
        raise LLMError(
            f"no API key for alias {spec.get('alias')!r} "
            f"(set one of: {', '.join(spec['api_key_env'])})")
    try:
        if provider == "anthropic":
            return _anthropic(spec, system, prompt, max_tokens, temperature)
        if provider == "openai":
            return _openai(spec, system, prompt, max_tokens, temperature)
        if provider == "gemini":
            return _gemini(spec, system, prompt, max_tokens, temperature)
        raise LLMError(f"unknown provider {provider!r}")
    except requests.RequestException as exc:
        raise LLMError(f"{provider} request failed: {exc}") from exc
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError(f"{provider} returned an unexpected payload: {exc}") from exc


def _anthropic(spec, system, prompt, max_tokens, temperature):
    url = spec["base_url"].rstrip("/") + "/v1/messages"
    headers = {
        "x-api-key": spec["api_key"],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": spec["model"],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    r = requests.post(url, headers=headers, json=body, timeout=config.HTTP_TIMEOUT)
    _raise_for_status(r)
    data = r.json()
    return "".join(b.get("text", "") for b in data["content"]).strip()


def _is_newer_openai(model):
    """GPT-5.x and o1/o3/o4 reasoning models use max_completion_tokens and
    reject a non-default temperature."""
    m = model.lower()
    return m.startswith(("gpt-5", "o1", "o3", "o4"))


def _openai(spec, system, prompt, max_tokens, temperature):
    base = spec["base_url"].rstrip("/")
    if not base:
        raise LLMError(
            f"alias {spec['alias']!r} has no base_url "
            f"(set MINICREW_{spec['alias'].upper()}_BASE_URL)")
    url = base + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {spec['api_key']}",
        "Content-Type": "application/json",
    }
    body = {
        "model": spec["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    # GPT-5 / o-series reasoning models renamed the token cap and only accept the
    # default temperature. Their *reasoning* tokens also draw from the same cap,
    # so a small budget yields an EMPTY visible answer — give a floor and keep
    # reasoning light so the visible reply actually fits.
    if _is_newer_openai(spec["model"]):
        body["max_completion_tokens"] = max(max_tokens, 8000)
        body["reasoning_effort"] = spec.get("reasoning_effort", "low")
    else:
        body["max_tokens"] = max_tokens
        body["temperature"] = temperature
    r = requests.post(url, headers=headers, json=body, timeout=config.HTTP_TIMEOUT)
    _raise_for_status(r)
    text = (r.json()["choices"][0]["message"].get("content") or "").strip()
    if not text:
        raise LLMError("empty response (raise max_tokens or lower reasoning_effort)")
    return text


def _is_thinking_gemini(model):
    """Gemini 2.5+ / 3.x think by default; thinking tokens draw from
    maxOutputTokens, so a small cap truncates the visible answer mid-sentence."""
    m = model.lower()
    return any(s in m for s in ("gemini-2.5", "gemini-3"))


def _gemini(spec, system, prompt, max_tokens, temperature):
    base = spec["base_url"].rstrip("/")
    url = f"{base}/models/{spec['model']}:generateContent?key={spec['api_key']}"
    if _is_thinking_gemini(spec["model"]):
        max_tokens = max(max_tokens, 8000)   # leave room for thoughts + answer
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    r = requests.post(url, json=body, timeout=config.HTTP_TIMEOUT)
    _raise_for_status(r)
    cand = r.json()["candidates"][0]
    parts = cand.get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        reason = cand.get("finishReason", "?")
        raise LLMError(f"empty response (finishReason={reason}; raise max_tokens)")
    return text


def _claude_cli(spec, system, prompt):
    """Run the local `claude` CLI in print mode — uses the Claude Code
    subscription, so no API key / no per-token API billing. `--system-prompt`
    *replaces* the default coding-assistant prompt so Claude plays the persona.
    """
    binary = spec.get("bin") or "claude"
    cmd = [binary, "-p", prompt, "--output-format", "text"]
    if system:
        cmd += ["--system-prompt", system]
    if spec.get("model"):
        cmd += ["--model", spec["model"]]
    # Run in a clean env so a *nested* Claude Code session (these vars set during
    # development) doesn't make the child behave as a sub-agent. Subscription
    # auth lives in ~/.claude, not in env, so this is safe.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CLAUDE", "CLAUDECODE", "AI_AGENT"))}
    if not shutil.which(binary) and not os.path.isfile(binary):
        raise LLMError(f"claude CLI {binary!r} not found "
                       f"(set MINICREW_CLAUDE_CLI_BIN to its path)")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=config.HTTP_TIMEOUT, env=env)
    except subprocess.TimeoutExpired as exc:
        raise LLMError("claude CLI timed out") from exc
    if res.returncode != 0:
        raise LLMError(f"claude CLI exited {res.returncode}: "
                       f"{(res.stderr or res.stdout)[:500]}")
    return res.stdout.strip()


def _b64(path):
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode()


def call_vision(spec, system, prompt, image_paths, max_tokens=4000):
    """Like call(), but with PNG images attached. Needs a multimodal API model
    (openai / gemini / anthropic) — claude_cli has no image input."""
    provider = spec["provider"]
    if provider == "claude_cli":
        raise LLMError("vision needs an API model — set the vision model to "
                       "openai / gemini / claude (not claude_cli)")
    if not spec.get("api_key"):
        raise LLMError(f"no API key for alias {spec.get('alias')!r}")
    try:
        if provider == "openai":
            return _openai_vision(spec, system, prompt, image_paths, max_tokens)
        if provider == "gemini":
            return _gemini_vision(spec, system, prompt, image_paths, max_tokens)
        if provider == "anthropic":
            return _anthropic_vision(spec, system, prompt, image_paths, max_tokens)
        raise LLMError(f"vision unsupported for provider {provider!r}")
    except requests.RequestException as exc:
        raise LLMError(f"{provider} vision request failed: {exc}") from exc
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError(f"{provider} vision payload error: {exc}") from exc


def _openai_vision(spec, system, prompt, image_paths, max_tokens):
    url = spec["base_url"].rstrip("/") + "/chat/completions"
    content = [{"type": "text", "text": prompt}]
    for p in image_paths:
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{_b64(p)}"}})
    body = {"model": spec["model"], "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": content}]}
    if _is_newer_openai(spec["model"]):
        body["max_completion_tokens"] = max(max_tokens, 8000)
        body["reasoning_effort"] = spec.get("reasoning_effort", "low")
    else:
        body["max_tokens"] = max_tokens
    r = requests.post(url, headers={"Authorization": f"Bearer {spec['api_key']}",
                      "Content-Type": "application/json"},
                      json=body, timeout=config.HTTP_TIMEOUT)
    _raise_for_status(r)
    text = (r.json()["choices"][0]["message"].get("content") or "").strip()
    if not text:
        raise LLMError("empty vision response (raise max_tokens)")
    return text


def _gemini_vision(spec, system, prompt, image_paths, max_tokens):
    base = spec["base_url"].rstrip("/")
    url = f"{base}/models/{spec['model']}:generateContent?key={spec['api_key']}"
    parts = [{"text": prompt}]
    for p in image_paths:
        parts.append({"inline_data": {"mime_type": "image/png", "data": _b64(p)}})
    if _is_thinking_gemini(spec["model"]):
        max_tokens = max(max_tokens, 8000)
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"maxOutputTokens": max_tokens}}
    r = requests.post(url, json=body, timeout=config.HTTP_TIMEOUT)
    _raise_for_status(r)
    cand = r.json()["candidates"][0]
    text = "".join(pt.get("text", "")
                   for pt in cand.get("content", {}).get("parts", [])).strip()
    if not text:
        raise LLMError(f"empty vision response (finishReason="
                       f"{cand.get('finishReason', '?')})")
    return text


def _anthropic_vision(spec, system, prompt, image_paths, max_tokens):
    url = spec["base_url"].rstrip("/") + "/v1/messages"
    content = [{"type": "text", "text": prompt}]
    for p in image_paths:
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/png", "data": _b64(p)}})
    body = {"model": spec["model"], "max_tokens": max_tokens, "system": system,
            "messages": [{"role": "user", "content": content}]}
    r = requests.post(url, headers={"x-api-key": spec["api_key"],
                      "anthropic-version": "2023-06-01",
                      "content-type": "application/json"},
                      json=body, timeout=config.HTTP_TIMEOUT)
    _raise_for_status(r)
    return "".join(b.get("text", "") for b in r.json()["content"]).strip()


def _raise_for_status(r):
    if r.status_code >= 400:
        # surface the provider's error body — it usually says exactly what's wrong
        detail = r.text[:500]
        raise LLMError(f"HTTP {r.status_code}: {detail}")
