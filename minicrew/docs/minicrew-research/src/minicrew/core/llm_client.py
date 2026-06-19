"""Unified LLM access for Claude, Gemini, and (later) local models.

Design note: the *only* thing the rest of the system knows about a model is
`complete(prompt, system) -> str`. That single seam is what makes the system
model-agnostic. Swapping Gemini for a local ELM is a config change, never a
code change above this file.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class ModelSpec:
    """A model's call-time identity. Loaded from configs/models.yaml later;
    hardcoded sensible defaults for the demo."""
    name: str          # friendly id, e.g. "claude"
    model: str         # litellm model string, e.g. "anthropic/claude-..."
    temperature: float = 0.3
    max_tokens: int = 2500


class LLMClient:
    def __init__(self, mock: bool = False):
        self.mock = mock

    def complete(self, spec: ModelSpec, *, system: str, prompt: str) -> str:
        if self.mock:
            # Deterministic fake. Lets you exercise the whole pipeline with
            # zero tokens and zero network. The reply echoes which agent ran
            # so transcripts are still legible.
            return (
                f"[MOCK {spec.name}] I reviewed the input ({len(prompt)} chars). "
                f"My single biggest concern would go here."
            )

        # Real call. LiteLLM gives one interface for every provider.
        from litellm import completion  # imported lazily so mock mode needs no deps

        resp = completion(
            model=spec.model,
            temperature=spec.temperature,
            max_tokens=spec.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return resp["choices"][0]["message"]["content"]


# Demo model registry. Real strings verified against current provider docs
# before you run live (these are placeholders you should confirm in Phase 4).
DEMO_MODELS = {
    "claude": ModelSpec(
        name="claude",
        model="anthropic/claude-opus-4-8",
        temperature=0.25,
    ),
    "gemini": ModelSpec(
        name="gemini",
        model="gemini/gemini-3.1-pro",
        temperature=0.30,
    ),
    "moderator": ModelSpec(
        name="moderator",
        model="anthropic/claude-opus-4-8",
        temperature=0.20,
    ),
}
