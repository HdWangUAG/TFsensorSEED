"""Compat shim — the legacy tool surface, now generated from the skill registry.

The real capabilities live in `skills_impl.py` (registered via `@skill`); the
framework is in `skills.py`. This module preserves the old API so the CLI
(`minicrew tool`) and the Streamlit chat page keep working unchanged:

- `REGISTRY[name]["fn"](**args)` returns the LEGACY plain dict (success payload,
  possibly with an `image`; or `{"error": ...}`) by unwrapping the rich
  SkillResult via `skills.to_legacy`.
- `openai_schemas(names)` is the OpenAI function-calling tool list.

New code should prefer `skills.call(name, **args)` to get the full SkillResult
(result + artifacts + provenance), which crews need.
"""
from __future__ import annotations

from . import skills
# Re-export the skill functions + data so existing `tools.<fn>` imports still work.
from .skills_impl import (  # noqa: F401
    KNOWN_SMILES, ligand_descriptors, ligand_similarity, interaction_fingerprint,
    train_model, analyze_structure,
)


# The original tool surface — what the CLI + chat page expose by default, so
# behaviour is unchanged. New/heavy skills (flexddg_score, retrodict) live in
# skills.SKILLS and are reached only via explicit allow-lists (P1 crews).
LEGACY_NAMES = ["ligand_descriptors", "ligand_similarity", "interaction_fingerprint",
                "analyze_structure", "train_model"]


def _legacy_fn(name):
    def fn(**kwargs):
        return skills.to_legacy(skills.call(name, **kwargs))
    return fn


# Built from SKILLS (single source of truth), restricted to the legacy surface.
REGISTRY = {
    name: {"fn": _legacy_fn(name), "description": skills.SKILLS[name].description,
           "parameters": skills.SKILLS[name].parameters}
    for name in LEGACY_NAMES if name in skills.SKILLS
}


def openai_schemas(names=None):
    """Tool list in OpenAI function-calling format (delegates to skills).
    Defaults to the legacy surface so CLI/chat behaviour is unchanged."""
    return skills.openai_schemas(names or LEGACY_NAMES)
