"""Ingest synthetic repair logs into the repair_logs Qdrant collection."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from dotenv import load_dotenv

from ingestion.embed_and_store import embed_texts, embedding_dimension
from vectorstore.qdrant_client import (
    COLLECTION_REPAIR_LOGS,
    build_point,
    ensure_collection,
    get_client,
    upsert_chunks,
)

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPAIR_LOGS_PATH = PROJECT_ROOT / "data" / "repair_logs" / "repair_logs.json"


def _log_to_text(entry: dict) -> str:
    return (
        f"Case ID: {entry['case_id']}\n"
        f"Equipment: {entry['equipment']}\n"
        f"Date: {entry['date']}\n"
        f"Issue: {entry['issue']}\n"
        f"Symptoms: {entry.get('symptoms', '')}\n"
        f"Root cause: {entry.get('root_cause', '')}\n"
        f"Solution applied: {entry['solution_applied']}\n"
        f"Downtime hours: {entry.get('downtime_hours', '')}\n"
        f"Technician: {entry.get('technician', '')}"
    )


def load_repair_logs(path: Path | None = None) -> list[dict]:
    log_path = path or REPAIR_LOGS_PATH
    with log_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def ingest_repair_logs(*, recreate: bool = False) -> int:
    entries = load_repair_logs()
    texts = [_log_to_text(entry) for entry in entries]
    vectors = embed_texts(texts)

    client = get_client()
    ensure_collection(
        client,
        COLLECTION_REPAIR_LOGS,
        embedding_dimension(),
        recreate=recreate,
    )

    points = []
    for entry, text, vector in zip(entries, texts, vectors):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, entry["case_id"]))
        points.append(
            build_point(
                point_id=point_id,
                vector=vector,
                payload={
                    "case_id": entry["case_id"],
                    "equipment": entry["equipment"],
                    "date": entry["date"],
                    "issue": entry["issue"],
                    "symptoms": entry.get("symptoms", ""),
                    "root_cause": entry.get("root_cause", ""),
                    "solution_applied": entry["solution_applied"],
                    "text": text,
                },
            )
        )

    return upsert_chunks(client, COLLECTION_REPAIR_LOGS, points)


if __name__ == "__main__":
    count = ingest_repair_logs(recreate=True)
    print(f"Stored {count} repair log entries in {COLLECTION_REPAIR_LOGS}")
