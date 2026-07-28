"""Embed parsed document chunks and store them in Qdrant collections."""

from __future__ import annotations

import os
import re
import time

from dotenv import load_dotenv
from qdrant_client import QdrantClient

from ingestion.parse_docs import (
    DocumentChunk,
    parse_all_documents,
    print_chunk_summary,
)
from vectorstore.qdrant_client import (
    COLLECTION_COMPLIANCE,
    COLLECTION_MANUALS,
    build_point,
    ensure_collection,
    get_client,
    upsert_chunks,
)

load_dotenv()

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
LOCAL_EMBEDDING_MODEL = os.getenv(
    "LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
)
USE_LOCAL_EMBEDDINGS = os.getenv("USE_LOCAL_EMBEDDINGS", "false").lower() in {
    "1",
    "true",
    "yes",
}
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "16"))
EMBED_REQUESTS_PER_MINUTE = int(os.getenv("EMBED_REQUESTS_PER_MINUTE", "90"))

_LOCAL_EMBEDDER = None


def _get_gemini_client():
    import google.generativeai as genai

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "Set GOOGLE_API_KEY or GEMINI_API_KEY for Gemini embeddings."
        )
    genai.configure(api_key=api_key)
    return genai


def _get_local_embedder():
    global _LOCAL_EMBEDDER
    if _LOCAL_EMBEDDER is None:
        from sentence_transformers import SentenceTransformer

        _LOCAL_EMBEDDER = SentenceTransformer(LOCAL_EMBEDDING_MODEL)
    return _LOCAL_EMBEDDER


def embedding_dimension() -> int:
    if USE_LOCAL_EMBEDDINGS:
        return 384
    return 3072


def _retry_delay_seconds(exc: Exception, attempt: int) -> float:
    message = str(exc)
    match = re.search(r"retry in ([0-9.]+)s", message, re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1.0
    return min(60.0, 2 ** attempt)


def embed_texts(
    texts: list[str],
    *,
    task_type: str = "retrieval_document",
) -> list[list[float]]:
    if not texts:
        return []

    if USE_LOCAL_EMBEDDINGS:
        model = _get_local_embedder()
        vectors = model.encode(
            texts,
            batch_size=EMBED_BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]

    from google.api_core import exceptions as google_exceptions

    genai = _get_gemini_client()
    vectors: list[list[float]] = []
    requests_this_minute = 0
    minute_started = time.monotonic()

    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]

        if requests_this_minute >= EMBED_REQUESTS_PER_MINUTE:
            elapsed = time.monotonic() - minute_started
            if elapsed < 60:
                time.sleep(60 - elapsed + 1)
            requests_this_minute = 0
            minute_started = time.monotonic()

        for attempt in range(8):
            try:
                result = genai.embed_content(
                    model=f"models/{EMBEDDING_MODEL}",
                    content=batch,
                    task_type=task_type,
                )
                batch_vectors = result.get("embedding")
                if batch_vectors and isinstance(batch_vectors[0], (int, float)):
                    vectors.append(batch_vectors)
                else:
                    vectors.extend(batch_vectors)
                requests_this_minute += len(batch)
                break
            except google_exceptions.ResourceExhausted as exc:
                if attempt == 7:
                    raise
                time.sleep(_retry_delay_seconds(exc, attempt))
            except Exception as exc:
                if attempt == 7:
                    raise
                time.sleep(_retry_delay_seconds(exc, attempt))

    return vectors


def embed_query(text: str) -> list[float]:
    vectors = embed_texts([text], task_type="retrieval_query")
    return vectors[0]


def collection_for_category(category: str) -> str:
    if category == "manual":
        return COLLECTION_MANUALS
    if category == "compliance":
        return COLLECTION_COMPLIANCE
    raise ValueError(f"Unknown category: {category}")


def store_chunks(
    chunks: list[DocumentChunk],
    *,
    client: QdrantClient | None = None,
    recreate_collections: bool = False,
) -> dict[str, int]:
    qdrant = client or get_client()
    vector_size = embedding_dimension()

    ensure_collection(
        qdrant, COLLECTION_MANUALS, vector_size, recreate=recreate_collections
    )
    ensure_collection(
        qdrant, COLLECTION_COMPLIANCE, vector_size, recreate=recreate_collections
    )

    texts = [chunk.text for chunk in chunks]
    vectors = embed_texts(texts)

    if len(vectors) != len(chunks):
        raise RuntimeError(
            f"Embedding count mismatch: {len(vectors)} vectors for {len(chunks)} chunks"
        )

    points_by_collection: dict[str, list] = {
        COLLECTION_MANUALS: [],
        COLLECTION_COMPLIANCE: [],
    }

    for chunk, vector in zip(chunks, vectors):
        collection = collection_for_category(chunk.category)
        points_by_collection[collection].append(
            build_point(
                point_id=chunk.id,
                vector=vector,
                payload=chunk.to_payload(),
            )
        )

    stored = {
        collection: upsert_chunks(qdrant, collection, points)
        for collection, points in points_by_collection.items()
        if points
    }
    return stored


def run_ingestion(
    *,
    recreate_collections: bool = False,
    client: QdrantClient | None = None,
) -> tuple[list[DocumentChunk], dict[str, int]]:
    chunks = parse_all_documents()
    print_chunk_summary(chunks)

    print(
        f"\nEmbedding with "
        f"{'local ' + LOCAL_EMBEDDING_MODEL if USE_LOCAL_EMBEDDINGS else EMBEDDING_MODEL}..."
    )
    stored = store_chunks(
        chunks,
        client=client,
        recreate_collections=recreate_collections,
    )

    print("\nStored points by collection:")
    for collection_name, count in stored.items():
        print(f"  {collection_name}: {count}")

    return chunks, stored


if __name__ == "__main__":
    run_ingestion(recreate_collections=True)
