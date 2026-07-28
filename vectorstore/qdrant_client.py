"""Qdrant client helpers for the ingestion pipeline."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

load_dotenv()

COLLECTION_MANUALS = "equipment_manuals"
COLLECTION_COMPLIANCE = "compliance_docs"
COLLECTION_REPAIR_LOGS = "repair_logs"

DEFAULT_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
DEFAULT_QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")


def get_client(url: str | None = None, api_key: str | None = None) -> QdrantClient:
    return QdrantClient(
        url=url or DEFAULT_QDRANT_URL,
        api_key=api_key or DEFAULT_QDRANT_API_KEY,
    )


def ensure_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int,
    *,
    recreate: bool = False,
) -> None:
    exists = client.collection_exists(collection_name)
    if recreate and exists:
        client.delete_collection(collection_name)
        exists = False

    if not exists:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


def upsert_chunks(
    client: QdrantClient,
    collection_name: str,
    points: list[PointStruct],
    *,
    batch_size: int = 64,
) -> int:
    for start in range(0, len(points), batch_size):
        batch = points[start : start + batch_size]
        client.upsert(collection_name=collection_name, points=batch)
    return len(points)


def build_point(
    point_id: str,
    vector: list[float],
    payload: dict[str, Any],
) -> PointStruct:
    return PointStruct(id=point_id, vector=vector, payload=payload)
