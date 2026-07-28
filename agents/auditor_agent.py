"""Auditor agent: cross-check proposed actions against compliance documents.

Supports two modes selected automatically by the caller:

  Judgment mode  — proposed_action is a non-empty string.
                   Retrieves compliance chunks relevant to the action and
                   returns structured findings with compliant:true/false verdicts.

  Factual QA mode — proposed_action is None.
                    Retrieves compliance chunks relevant to the raw user query
                    and returns a plain answer string (no compliance verdict).
                    Used for definition/information lookups such as
                    "What is a Gate Safety Plug?" or
                    "What are the 7 safety features on the electrical unit?"
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from agents.llm_client import generate_json, generate_text
from vectorstore.qdrant_client import COLLECTION_COMPLIANCE
from vectorstore.retrieval import retrieve_top_k

TOP_K = 4


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class AuditFinding:
    clause_id: str
    relevance: str
    compliant: bool
    reasoning: str


@dataclass
class AuditorResult:
    """Unified result container for both auditor modes.

    Judgment mode:  findings is populated, answer is None.
    Factual QA mode: answer is populated, findings is empty.
    """
    proposed_action: str | None
    query: str
    mode: str                                        # "judgment" | "factual_qa"
    findings: list[AuditFinding] = field(default_factory=list)
    answer: str | None = None
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposed_action": self.proposed_action,
            "query": self.query,
            "mode": self.mode,
            "findings": [asdict(f) for f in self.findings],
            "answer": self.answer,
            "retrieved_chunks": self.retrieved_chunks,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_context(chunks: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        source = chunk.get("source_file", "unknown")
        chunk_index = chunk.get("chunk_index", "?")
        blocks.append(
            f"[Clause {index}] id={source}#{chunk_index}\n{chunk.get('text', '')}"
        )
    return "\n\n".join(blocks)


# ── Judgment mode ─────────────────────────────────────────────────────────────

def _run_judgment(
    query: str,
    proposed_action: str,
    chunks: list[dict[str, Any]],
) -> AuditorResult:
    """Evaluate a proposed_action against retrieved compliance clauses."""
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
        query=query,
        mode="judgment",
        findings=findings,
        answer=None,
        retrieved_chunks=chunks,
    )


# ── Factual QA mode ───────────────────────────────────────────────────────────

def _run_factual_qa(
    query: str,
    chunks: list[dict[str, Any]],
) -> AuditorResult:
    """Answer a factual safety/compliance question from retrieved compliance chunks."""
    context = _format_context(chunks)

    prompt = f"""You are a safety compliance expert for hydraulic press machinery.
Answer the following question using ONLY the compliance document excerpts provided.
Cite each relevant excerpt by its clause id (source_file#chunk_index).
Be specific and complete — list all items if the question asks for a numbered list.
Do not invent information not present in the excerpts.

Question:
{query}

Compliance excerpts:
{context}

Write a clear, well-structured answer in plain prose or bullet points as appropriate.
"""

    answer = generate_text(prompt, thinking_level="medium")

    return AuditorResult(
        proposed_action=None,
        query=query,
        mode="factual_qa",
        findings=[],
        answer=answer,
        retrieved_chunks=chunks,
    )


# ── Public entry point ────────────────────────────────────────────────────────

def run_auditor(
    query: str,
    *,
    proposed_action: str | None = None,
    top_k: int = TOP_K,
) -> AuditorResult:
    """Route to judgment or factual-QA mode based on whether proposed_action is set.

    Parameters
    ----------
    query:
        The raw user query. Always provided. Used as retrieval text in
        factual-QA mode; used to populate AuditorResult.query in judgment mode.
    proposed_action:
        When set (non-empty), judgment mode is used: the action is evaluated
        against compliance clauses and compliant:true/false findings are returned.
        When None, factual-QA mode is used: the query is answered directly from
        retrieved compliance content without a compliance verdict.
    """
    # Decide retrieval query and mode
    if proposed_action:
        retrieval_query = proposed_action
        mode = "judgment"
    else:
        retrieval_query = query
        mode = "factual_qa"

    chunks = retrieve_top_k(COLLECTION_COMPLIANCE, retrieval_query, top_k=top_k)

    if mode == "judgment":
        return _run_judgment(query, proposed_action, chunks)   # type: ignore[arg-type]
    else:
        return _run_factual_qa(query, chunks)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        test_input = sys.argv[1]
    else:
        test_input = "Operator bypasses the safety guard to speed up production."

    # Demonstrate judgment mode
    result = run_auditor(test_input, proposed_action=test_input)
    print(json.dumps(result.to_dict(), indent=2))
