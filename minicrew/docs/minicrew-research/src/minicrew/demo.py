"""Demo runner. Smoke-test in mock mode (free, no keys), then flip to real.

    # mock — runs offline, proves the wiring:
    python -m minicrew.demo --file examples/steroid_project/plan.md --mock

    # real — needs ANTHROPIC_API_KEY and GEMINI_API_KEY in env:
    python -m minicrew.demo --file examples/steroid_project/plan.md
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .core.crew import Agent, Crew, RunContext
from .core.llm_client import DEMO_MODELS, LLMClient
from .core.logger import save_run

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = ROOT / "prompts"


def build_crew() -> Crew:
    claude = Agent("claude_biophysics",
                   (PROMPTS / "claude_biophysics_reviewer.md").read_text(),
                   DEMO_MODELS["claude"])
    gemini = Agent("gemini_challenger",
                   (PROMPTS / "gemini_challenger.md").read_text(),
                   DEMO_MODELS["gemini"])
    moderator = Agent("moderator",
                      (PROMPTS / "elm_moderator.md").read_text(),
                      DEMO_MODELS["moderator"])
    return Crew(
        reviewers=[claude, gemini],
        moderator=moderator,
        reviewer_task="Review this material per your role. Be concrete and severity-ordered.",
        moderator_task="Synthesize the two reviews into the required sections.",
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--mock", action="store_true", help="deterministic, no API calls")
    args = ap.parse_args()

    user_input = Path(args.file).read_text()
    ctx = RunContext(user_input=user_input)        # evidence="" for now (v1)
    crew = build_crew()
    llm = LLMClient(mock=args.mock)

    crew.run_parallel_blind(ctx, llm, on_step=lambda s: print(f"  -> {s}"))
    record = save_run(ctx, "steroid_plan_review", "parallel_blind", ROOT)
    print(f"\nsaved: conversations/{record['run_id']}.md")
    print(f"saved: runs/{record['run_id']}.json")


if __name__ == "__main__":
    main()
