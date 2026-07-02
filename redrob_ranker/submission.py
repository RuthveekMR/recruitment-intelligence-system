"""Submission CSV generation and guardrails."""

from __future__ import annotations

import csv
from pathlib import Path

from .explainability import build_reasoning
from .ranking import RankedCandidate

HEADER = ["candidate_id", "rank", "score", "reasoning"]


def validate_ranked_rows(rows: list[RankedCandidate], expected_rows: int) -> None:
    """Internal guardrail before writing the CSV."""

    if len(rows) != expected_rows:
        raise ValueError(f"Expected {expected_rows} ranked rows, found {len(rows)}")
    ids = [row.candidate.candidate_id for row in rows]
    ranks = [row.rank for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate candidate_id in ranked rows")
    if ranks != list(range(1, expected_rows + 1)):
        raise ValueError("Ranks must be exactly 1..N")
    scores = [row.score for row in rows]
    for left, right in zip(scores, scores[1:]):
        if left < right:
            raise ValueError("Scores must be non-increasing")
    for left, right in zip(rows, rows[1:]):
        if left.score == right.score and left.candidate.candidate_id > right.candidate.candidate_id:
            raise ValueError("Equal-score tie-break must use candidate_id ascending")


def write_submission(rows: list[RankedCandidate], path: str | Path, expected_rows: int, max_reasoning_chars: int) -> None:
    """Write the challenge-compliant CSV."""

    validate_ranked_rows(rows, expected_rows)
    out_path = Path(path)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        for row in rows:
            writer.writerow(
                [
                    row.candidate.candidate_id,
                    row.rank,
                    f"{row.score:.6f}",
                    build_reasoning(row, max_reasoning_chars),
                ]
            )
