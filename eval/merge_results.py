"""Merge partial full eval with retry CSV into one ordered results file."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVAL_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FIELDNAMES = [
    "query_id",
    "category",
    "query",
    "expected_agents",
    "actual_agents",
    "routing_match",
    "error",
    "synthesized_answer",
]


def load_csv(path: Path) -> dict[str, dict]:
    return {row["query_id"]: row for row in csv.DictReader(path.open(encoding="utf-8"))}


def main() -> None:
    queries_path = EVAL_DIR / "test_queries.json"
    partial_path = EVAL_DIR / "eval_results_full_pre_retry.csv"
    retry_path = EVAL_DIR / "eval_results_retry.csv"
    output_path = EVAL_DIR / "eval_results_full.csv"

    query_order = [item["id"] for item in json.loads(queries_path.read_text(encoding="utf-8"))["queries"]]
    partial = load_csv(partial_path)
    retry = load_csv(retry_path)

    retry_ids = set(retry)
    merged: dict[str, dict] = {}

    for qid, row in partial.items():
        if row.get("error", "").strip():
            continue
        merged[qid] = row

    for qid, row in retry.items():
        merged[qid] = row

    missing = [qid for qid in query_order if qid not in merged]
    if missing:
        raise SystemExit(f"Missing rows after merge: {', '.join(missing)}")

    rows = [merged[qid] for qid in query_order]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Merged {len(rows)} rows -> {output_path}")
    print(f"  From partial (no error): {len(merged) - len(retry_ids)}")
    print(f"  From retry:              {len(retry_ids)}")


if __name__ == "__main__":
    main()
