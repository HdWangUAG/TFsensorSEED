"""The heart of MiniCrew: agents, the shared context, and the two topologies.

This file is where the multi-agent *design* lives. Read it slowly — the
interesting decisions are commented inline, not hidden.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .llm_client import LLMClient, ModelSpec


@dataclass
class Agent:
    """An agent is nothing but a role: a name, a system prompt, and a model.

    The system prompt is what makes an agent 'critical' or 'synthesizing'.
    That is the cheapest and most powerful lever in the whole system —
    sharper prompt, sharper agent, no extra orchestration needed.
    """
    name: str
    system: str
    model: ModelSpec


@dataclass
class AgentOutput:
    agent: str
    prompt_seen: str   # EXACTLY what this agent received. This is the learning instrument.
    reply: str


@dataclass
class RunContext:
    """Holds the original input and every agent's output.

    DESIGN DECISION (the one the original plan skipped): in parallel-blind
    review, reviewer agents see ONLY the user input — never each other's
    replies. Only the moderator sees the reviews. `reviewer_prompt` and
    `moderator_prompt` below encode that information boundary explicitly.
    Change these two methods and you change the entire system's character.
    """
    user_input: str
    evidence: str = ""        # empty in v1. Later: paper claims / assay numbers.
    outputs: list[AgentOutput] = field(default_factory=list)

    def reviewer_prompt(self, task: str) -> str:
        """What an independent reviewer sees: the input + its task + evidence.
        Crucially, NOT the other reviewer's opinion."""
        parts = [f"## Material to review\n{self.user_input}"]
        if self.evidence.strip():
            parts.append(f"## Grounding evidence (treat as more reliable than your priors)\n{self.evidence}")
        parts.append(f"## Your task\n{task}")
        return "\n\n".join(parts)

    def moderator_prompt(self, task: str) -> str:
        """What the moderator sees: the original input + every review.
        Its job is to surface agreement/disagreement, not manufacture consensus."""
        parts = [f"## Original material\n{self.user_input}"]
        if self.evidence.strip():
            parts.append(f"## Grounding evidence\n{self.evidence}")
        for o in self.outputs:
            parts.append(f"## Review by {o.agent}\n{o.reply}")
        parts.append(f"## Your task\n{task}")
        return "\n\n".join(parts)


@dataclass
class Crew:
    """Orchestrates agents over a context. Two topologies, one comparison."""
    reviewers: list[Agent]
    moderator: Agent
    reviewer_task: str
    moderator_task: str

    def run_parallel_blind(self, ctx: RunContext, llm: LLMClient,
                           on_step: Callable[[str], None] = lambda _: None) -> RunContext:
        """Each reviewer critiques the input independently (blind to others),
        then the moderator synthesizes. Genuinely uncorrelated opinions."""
        for agent in self.reviewers:
            on_step(f"reviewing: {agent.name}")
            prompt = ctx.reviewer_prompt(self.reviewer_task)
            reply = llm.complete(agent.model, system=agent.system, prompt=prompt)
            ctx.outputs.append(AgentOutput(agent.name, prompt, reply))

        on_step(f"synthesizing: {self.moderator.name}")
        mod_prompt = ctx.moderator_prompt(self.moderator_task)
        mod_reply = llm.complete(self.moderator.model, system=self.moderator.system, prompt=mod_prompt)
        ctx.outputs.append(AgentOutput(self.moderator.name, mod_prompt, mod_reply))
        return ctx
