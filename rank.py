#!/usr/bin/env python3
"""Command-line entrypoint for Redrob offline candidate ranking."""

from __future__ import annotations

import argparse
import sys

from redrob_ranker.config import RankerConfig
from redrob_ranker.logging_utils import configure_logging
from redrob_ranker.orchestrator import run_pipeline


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Produce a Redrob top-100 submission CSV.")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out", required=True, help="Path to output CSV")
    parser.add_argument("--job", default=None, help="Optional path to job_description.docx")
    parser.add_argument("--config", default=None, help="Optional JSON config override")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    configure_logging(args.verbose)
    config = RankerConfig.from_json(args.config)
    run_pipeline(args.candidates, args.out, config, job_path=args.job)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
