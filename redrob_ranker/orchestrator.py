"""Pipeline orchestration for the offline multi-agent architecture."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import time

from .behavior import score_behavior
from .candidate import iter_candidates
from .config import RankerConfig
from .job_understanding import load_job_profile
from .ranking import RankedCandidate, rank_retrieved
from .retrieval import retrieve_candidates
from .submission import write_submission

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    """Runtime result summary."""

    rows: list[RankedCandidate]
    candidates_seen: int
    retrieval_pool_size: int
    elapsed_seconds: float


def run_pipeline(candidates_path: str, out_path: str, config: RankerConfig, job_path: str | None = None) -> PipelineResult:
    """Run the full deterministic ranking pipeline and write submission CSV."""

    started = time.perf_counter()
    job = load_job_profile(job_path)
    seen = 0

    def scored_candidates():
        nonlocal seen
        for candidate in iter_candidates(candidates_path):
            seen += 1
            if seen % 20000 == 0:
                LOGGER.info("Parsed and behavior-scored %s candidates", seen)
            behavior = score_behavior(
                candidate,
                today=config.evaluation_date,
                weights=config.behavior_weights,
                hard_filter_open_to_work=config.hard_filter_open_to_work,
            )
            yield candidate, behavior

    LOGGER.info("Starting hybrid retrieval from %s", candidates_path)
    retrieved = retrieve_candidates(scored_candidates(), job, config.retrieval_pool_size)
    LOGGER.info("Retrieved %s candidates for final scoring", len(retrieved))
    final_pool = retrieved[: config.final_review_pool] if config.final_review_pool else retrieved
    ranked = rank_retrieved(final_pool, job, config.ranking_weights, config.output_rows)
    if len(ranked) < config.output_rows:
        raise RuntimeError(f"Only produced {len(ranked)} ranked candidates from {seen} records")
    write_submission(ranked, out_path, config.output_rows, config.max_reasoning_chars)
    elapsed = time.perf_counter() - started
    LOGGER.info("Wrote %s rows to %s in %.2fs", len(ranked), Path(out_path), elapsed)
    return PipelineResult(rows=ranked, candidates_seen=seen, retrieval_pool_size=len(retrieved), elapsed_seconds=elapsed)
