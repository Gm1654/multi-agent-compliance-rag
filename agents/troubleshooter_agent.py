"""Troubleshooter agent: match current issues to past repair logs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from vectorstore.qdrant_client import COLLECTION_REPAIR_LOGS
from vectorstore.retrieval import retrieve_top_k

TOP_K = 3


@dataclass
class TroubleshooterMatch:
    past_case_id: str
    similarity_score: float
    issue: str
    solution_applied: str


@dataclass
class TroubleshooterResult:
    query: str
    matches: list[TroubleshooterMatch] = field(default_factory=list)
    retrieved_logs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "matches": [asdict(match) for match in self.matches],
            "retrieved_logs": self.retrieved_logs,
        }


def run_troubleshooter(query: str, *, top_k: int = TOP_K) -> TroubleshooterResult:
    logs = retrieve_top_k(COLLECTION_REPAIR_LOGS, query, top_k=top_k)
    matches = [
        TroubleshooterMatch(
            past_case_id=log.get("case_id", "unknown"),
            similarity_score=float(log.get("score", 0.0)),
            issue=log.get("issue", ""),
            solution_applied=log.get("solution_applied", ""),
        )
        for log in logs
    ]

    return TroubleshooterResult(
        query=query,
        matches=matches,
        retrieved_logs=logs,
    )


if __name__ == "__main__":
    import sys

    test_query = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "The ram slowly drifts down and the pump feels spongy."
    )
    result = run_troubleshooter(test_query)
    print(json.dumps(result.to_dict(), indent=2))
