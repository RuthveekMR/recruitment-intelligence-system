"""Local submission audit beyond the official format validator."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics
import sys

from .submission import HEADER


def load_candidate_ids(path: str | Path) -> set[str]:
    """Load candidate IDs from JSONL or a JSON sample array."""

    ids: set[str] = set()
    source = Path(path)
    if source.suffix.lower() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        records = payload if isinstance(payload, list) else [payload]
        for record in records:
            ids.add(str(record.get("candidate_id", "")))
        return ids

    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
            ids.add(str(record.get("candidate_id", "")))
    return ids


def audit_submission(csv_path: str | Path, candidates_path: str | Path, expected_rows: int = 100) -> list[str]:
    """Return a list of audit issues; empty means the local audit passed."""

    issues: list[str] = []
    valid_ids = load_candidate_ids(candidates_path)
    rows: list[dict[str, str]] = []
    with Path(csv_path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != HEADER:
            issues.append(f"Header mismatch: expected {HEADER}, found {reader.fieldnames}")
        for row in reader:
            rows.append(row)

    if len(rows) != expected_rows:
        issues.append(f"Expected {expected_rows} rows, found {len(rows)}")

    ids = [row.get("candidate_id", "") for row in rows]
    missing_ids = [cid for cid in ids if cid not in valid_ids]
    if missing_ids:
        issues.append(f"Candidate IDs not found in source data: {missing_ids[:5]}")
    if len(set(ids)) != len(ids):
        issues.append("Duplicate candidate_id values present")

    scores: list[float] = []
    for row in rows:
        try:
            scores.append(float(row.get("score", "")))
        except ValueError:
            issues.append(f"Non-numeric score for {row.get('candidate_id')}")
    for left, right in zip(scores, scores[1:]):
        if left < right:
            issues.append("Scores are not monotonically non-increasing")
            break
    if scores and len(set(scores)) < min(10, len(scores)):
        issues.append("Scores have very low variation")

    reasonings = [row.get("reasoning", "").strip() for row in rows]
    empty = sum(1 for text in reasonings if not text)
    if empty:
        issues.append(f"{empty} rows have empty reasoning")
    unique_reasonings = len(set(reasonings))
    if unique_reasonings < min(90, len(reasonings)):
        issues.append(f"Reasoning variation is low: {unique_reasonings} unique strings")
    short_reasonings = sum(1 for text in reasonings if len(text.split()) < 12)
    if short_reasonings:
        issues.append(f"{short_reasonings} rows have very short reasoning")

    return issues


def summarize_submission(csv_path: str | Path) -> str:
    """Create a compact score summary for logs and README verification."""

    with Path(csv_path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    scores = [float(row["score"]) for row in rows]
    titles = [row["reasoning"].split(" with ", 1)[0] for row in rows if " with " in row["reasoning"]]
    title_counts: dict[str, int] = {}
    for title in titles:
        title_counts[title] = title_counts.get(title, 0) + 1
    top_titles = sorted(title_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
    return (
        f"rows={len(rows)}, score_min={min(scores):.6f}, score_median={statistics.median(scores):.6f}, "
        f"score_max={max(scores):.6f}, top_titles={top_titles}"
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit a Redrob submission against the candidate pool.")
    parser.add_argument("--submission", required=True, help="Path to submission CSV")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl or sample JSON")
    parser.add_argument("--expected-rows", type=int, default=100, help="Expected number of ranked rows")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    issues = audit_submission(args.submission, args.candidates, expected_rows=args.expected_rows)
    print(summarize_submission(args.submission))
    if issues:
        print("Audit failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
