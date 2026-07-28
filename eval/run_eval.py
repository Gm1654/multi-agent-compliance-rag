"""Run routing eval over eval/test_queries.json (orchestrator + synthesizer, same as Streamlit UI)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.synthesizer import answer_query

DEFAULT_QUERIES_PATH = Path(__file__).resolve().parent / "test_queries.json"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent / "eval_results.csv"


def _normalize_agents(agents: list[str]) -> list[str]:
    return sorted({a.strip().lower() for a in agents if a})


def _agents_match(expected: list[str], actual: list[str]) -> bool:
    return _normalize_agents(expected) == _normalize_agents(actual)


def _format_agents(agents: list[str]) -> str:
    return "|".join(_normalize_agents(agents))


def load_queries(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["queries"]


def select_queries(
    all_queries: list[dict],
    *,
    ids: list[str] | None = None,
    limit: int | None = None,
) -> list[dict]:
    if ids:
        by_id = {item["id"]: item for item in all_queries}
        missing = [qid for qid in ids if qid not in by_id]
        if missing:
            raise SystemExit(f"Unknown query id(s): {', '.join(missing)}")
        selected = [by_id[qid] for qid in ids]
    else:
        selected = list(all_queries)
    if limit is not None:
        selected = selected[:limit]
    return selected


def run_eval(
    queries_path: Path,
    output_path: Path,
    *,
    ids: list[str] | None = None,
    limit: int | None = None,
    delay: float = 0.0,
) -> list[dict]:
    queries = select_queries(load_queries(queries_path), ids=ids, limit=limit)

    rows: list[dict] = []
    total = len(queries)

    for index, item in enumerate(queries, start=1):
        query_id = item["id"]
        query_text = item["query"]
        expected = item.get("expected_agents", [])

        print(f"[{index}/{total}] {query_id} ...", flush=True)

        try:
            result = answer_query(query_text)
            actual = result.agents_used
            answer = result.final_answer
            error = ""
        except Exception as exc:
            actual = []
            answer = ""
            error = str(exc)

        match = _agents_match(expected, actual) if not error else False

        row = {
            "query_id": query_id,
            "category": item.get("category", ""),
            "query": query_text,
            "expected_agents": _format_agents(expected),
            "actual_agents": _format_agents(actual),
            "routing_match": "yes" if match else "no",
            "error": error,
            "synthesized_answer": answer,
        }
        rows.append(row)

        if delay > 0 and index < total:
            time.sleep(delay)

    fieldnames = [
        "query_id",
        "category",
        "query",
        "expected_agents",
        "actual_agents",
        "routing_match",
        "error",
        "synthesized_answer",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return rows


def print_summary(rows: list[dict]) -> None:
    total = len(rows)
    matched = sum(1 for row in rows if row["routing_match"] == "yes")
    errors = sum(1 for row in rows if row["error"])
    pct = (100.0 * matched / total) if total else 0.0

    print()
    print("=== Eval summary ===")
    print(f"Total queries:     {total}")
    print(f"Routing matches:   {matched}")
    print(f"Routing mismatches:{total - matched - errors}")
    print(f"Errors:            {errors}")
    print(f"Routing accuracy:  {pct:.1f}% ({matched}/{total})")

    mismatches = [r for r in rows if r["routing_match"] == "no" and not r["error"]]
    if mismatches:
        print()
        print("Routing mismatches:")
        for row in mismatches:
            print(
                f"  {row['query_id']}: expected [{row['expected_agents']}] "
                f"got [{row['actual_agents']}]"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run orchestrator routing eval (full pipeline via answer_query)."
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=DEFAULT_QUERIES_PATH,
        help="Path to test_queries.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to write CSV results",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N queries after --ids filtering (optional)",
    )
    parser.add_argument(
        "--ids",
        type=str,
        default=None,
        help="Comma-separated query ids to run, in order (e.g. R01,R03,A02,M01)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Seconds to wait between queries (e.g. 6 to stay under Gemini free-tier RPM)",
    )
    args = parser.parse_args()

    id_list = [part.strip() for part in args.ids.split(",") if part.strip()] if args.ids else None

    print(f"Queries: {args.queries}")
    print(f"Output:  {args.output}")
    if id_list:
        print(f"Ids:     {', '.join(id_list)}")
    elif args.limit:
        print(f"Limit:   {args.limit}")
    if args.delay:
        print(f"Delay:   {args.delay}s between queries")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print()

    rows = run_eval(
        args.queries,
        args.output,
        ids=id_list,
        limit=args.limit,
        delay=args.delay,
    )
    print_summary(rows)
    print()
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
