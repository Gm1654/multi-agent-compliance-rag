"""Response synthesizer: combine specialist agent outputs into one answer."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from agents.llm_client import generate_text
from agents.orchestrator import OrchestratorResult, run_orchestrator


@dataclass
class SynthesizerResult:
    query: str
    final_answer: str
    agents_used: list[str]
    orchestrator: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def synthesize_response(orchestrator_result: OrchestratorResult) -> SynthesizerResult:
    payload = orchestrator_result.to_dict()
    prompt = f"""You are the response synthesizer for a hydraulic press maintenance assistant.
Combine the specialist agent outputs below into one clear, coherent answer for the technician.

Requirements:
- Lead with the most actionable guidance
- Preserve important safety warnings from the auditor
- Mention relevant past repair cases when troubleshooter results exist
- Cite manual sources when researcher results exist
- Do not invent facts not present in the agent outputs
- Use concise sections and bullet points where helpful

User query:
{orchestrator_result.query}

Agent outputs JSON:
{json.dumps(payload, indent=2)}
"""

    final_answer = generate_text(prompt, thinking_level="medium")
    return SynthesizerResult(
        query=orchestrator_result.query,
        final_answer=final_answer,
        agents_used=orchestrator_result.plan.agents,
        orchestrator=payload,
    )


def answer_query(query: str) -> SynthesizerResult:
    orchestrator_result = run_orchestrator(query)
    return synthesize_response(orchestrator_result)


if __name__ == "__main__":
    import sys

    test_query = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "The ram drifts down and feels spongy. Is it safe to keep using the press?"
    )
    result = answer_query(test_query)
    print(json.dumps(result.to_dict(), indent=2))
