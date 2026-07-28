"""Auditor agent: cross-check proposed actions against compliance documents."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from agents.llm_client import generate_json
from vectorstore.qdrant_client import COLLECTION_COMPLIANCE
from vectorstore.retrieval import retrieve_top_k

TOP_K = 4


@dataclass
class AuditFinding:
    clause_id: str
    relevance: str
    compliant: bool
    reasoning: str


@dataclass
class AuditorResult:
    proposed_action: str
    findings: list[AuditFinding] = field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposed_action": self.proposed_action,
            "findings": [asdict(f) for f in self.findings],
            "retrieved_chunks": self.retrieved_chunks,
        }


def _format_context(chunks: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        source = chunk.get("source_file", "unknown")
        chunk_index = chunk.get("chunk_index", "?")
        blocks.append(
            f"[Clause {index}] id={source}#{chunk_index}\n{chunk.get('text', '')}"
        )
    return "\n\n".join(blocks)


def run_auditor(proposed_action: str, *, top_k: int = TOP_K) -> AuditorResult:
    chunks = retrieve_top_k(COLLECTION_COMPLIANCE, proposed_action, top_k=top_k)
    context = _format_context(chunks)

    prompt = f"""You are a safety compliance auditor for hydraulic press machinery.
Given the proposed action and compliance excerpts, identify matching or conflicting clauses.

Return ONLY valid JSON with this shape:
{{
  "findings": [
    {{
      "clause_id": "source_file#chunk_index",
      "relevance": "high|medium|low",
      "compliant": true,
      "reasoning": "brief explanation"
    }}
  ]
}}

Rules:
- Use clause_id format like "Guidelines-on-Safe-Use-of-Press-Machines-2015.pdf#12"
- Set compliant=false if the action violates or conflicts with the clause
- Set compliant=true if the clause supports or requires the action
- Include one finding per relevant excerpt when possible

Proposed action:
{proposed_action}

Compliance excerpts:
{context}
"""

    parsed = generate_json(prompt, thinking_level="medium")
    findings = [
        AuditFinding(
            clause_id=item.get("clause_id", "unknown"),
            relevance=item.get("relevance", "medium"),
            compliant=bool(item.get("compliant", False)),
            reasoning=item.get("reasoning", ""),
        )
        for item in parsed.get("findings", [])
    ]

    return AuditorResult(
        proposed_action=proposed_action,
        findings=findings,
        retrieved_chunks=chunks,
    )


if __name__ == "__main__":
    import sys

    test_action = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "Operator bypasses the safety guard to speed up production."
    )
    result = run_auditor(test_action)
    print(json.dumps(result.to_dict(), indent=2))
