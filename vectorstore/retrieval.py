"""Vector search helpers shared by agents."""

from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient

from ingestion.embed_and_store import embed_query
from vectorstore.qdrant_client import get_client


def retrieve_top_k(
    collection_name: str,
    query: str,
    *,
    top_k: int = 4,
    client: QdrantClient | None = None,
) -> list[dict[str, Any]]:
    qdrant = client or get_client()
    vector = embed_query(query)
    hits = qdrant.query_points(
        collection_name=collection_name,
        query=vector,
        limit=top_k,
        with_payload=True,
    ).points

    results: list[dict[str, Any]] = []
    for hit in hits:
        payload = dict(hit.payload or {})
        payload["score"] = hit.score
        payload["point_id"] = str(hit.id)
        results.append(payload)
    return results
