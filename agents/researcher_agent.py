"""Researcher agent: retrieve from equipment manuals and answer with citations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from agents.llm_client import generate_text
from vectorstore.qdrant_client import COLLECTION_MANUALS
from vectorstore.retrieval import retrieve_top_k

TOP_K = 4


@dataclass
class ResearcherResult:
    query: str
    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _format_context(chunks: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        source = chunk.get("source_file", "unknown")
        chunk_index = chunk.get("chunk_index", "?")
        pages = chunk.get("page_numbers", [])
        page_text = f", pages {pages}" if pages else ""
        blocks.append(
            f"[Source {index}] file={source}, chunk={chunk_index}{page_text}\n"
            f"{chunk.get('text', '')}"
        )
    return "\n\n".join(blocks)


def run_researcher(query: str, *, top_k: int = TOP_K) -> ResearcherResult:
    chunks = retrieve_top_k(COLLECTION_MANUALS, query, top_k=top_k)
    context = _format_context(chunks)

    prompt = f"""You are a technical researcher for hydraulic press maintenance.
Answer the user's question using ONLY the manual excerpts below.
If the excerpts do not contain enough information, say what is missing.
Cite sources inline like [Source 1] matching the excerpt labels.

Question:
{query}

Manual excerpts:
{context}
"""

    answer = generate_text(prompt, thinking_level="low")

    sources = [
        {
            "source_file": chunk.get("source_file"),
            "chunk_index": chunk.get("chunk_index"),
            "page_numbers": chunk.get("page_numbers", []),
            "score": chunk.get("score"),
        }
        for chunk in chunks
    ]

    return ResearcherResult(
        query=query,
        answer=answer,
        sources=sources,
        retrieved_chunks=chunks,
    )


if __name__ == "__main__":
    import sys

    test_query = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "How do I safely operate the hydraulic press?"
    )
    result = run_researcher(test_query)
    print(json.dumps(result.to_dict(), indent=2))
