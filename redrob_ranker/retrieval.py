"""Hybrid lexical, ontology, and metadata retrieval."""

from __future__ import annotations

from dataclasses import dataclass
import heapq
from typing import Iterable

from .behavior import BehaviorScore
from .candidate import CandidateFacts
from .job_understanding import JobProfile
from .ontology import has_technical_title, is_product_industry, is_service_company
from .representation import MultiVector, candidate_vector, job_vector, weighted_overlap
from .text import clamp


@dataclass(frozen=True)
class RetrievedCandidate:
    """Candidate retained for final scoring."""

    candidate: CandidateFacts
    retrieval_score: float
    behavior: BehaviorScore


def score_retrieval(candidate: CandidateFacts, candidate_mv: MultiVector, job_mv: MultiVector, job: JobProfile) -> float:
    """Compute a broad-recall hybrid retrieval score."""

    summary = weighted_overlap(candidate_mv.summary, job_mv.summary)
    skills = weighted_overlap(candidate_mv.skills, job_mv.skills)
    experience = weighted_overlap(candidate_mv.experience, job_mv.experience)
    ontology = weighted_overlap(candidate_mv.ontology, job_mv.ontology)
    metadata = 0.0
    if has_technical_title(candidate.current_title):
        metadata += 0.22
    if is_product_industry(candidate.current_industry):
        metadata += 0.14
    if not is_service_company(candidate.current_company):
        metadata += 0.06
    if job.ideal_years_min <= candidate.years_of_experience <= job.ideal_years_max:
        metadata += 0.16
    elif 4.0 <= candidate.years_of_experience <= 10.5:
        metadata += 0.08

    return clamp(0.25 * skills + 0.28 * experience + 0.20 * ontology + 0.12 * summary + metadata)


def retrieve_candidates(
    candidates: Iterable[tuple[CandidateFacts, BehaviorScore]],
    job: JobProfile,
    pool_size: int,
    include_hard_filtered_fallback: bool = False,
) -> list[RetrievedCandidate]:
    """Stream candidates and keep the strongest retrieval pool in memory."""

    job_mv = job_vector(job)
    heap: list[tuple[float, str, RetrievedCandidate]] = []
    fallback_heap: list[tuple[float, str, RetrievedCandidate]] = []

    for candidate, behavior in candidates:
        mv = candidate_vector(candidate)
        score = score_retrieval(candidate, mv, job_mv, job)
        if behavior.hard_filtered and not include_hard_filtered_fallback:
            target = fallback_heap
            adjusted = score * 0.35
        else:
            target = heap
            adjusted = score * (0.82 + 0.28 * behavior.score)
        item = RetrievedCandidate(candidate=candidate, retrieval_score=adjusted, behavior=behavior)
        heapq.heappush(target, (adjusted, candidate.candidate_id, item))
        if len(target) > pool_size:
            heapq.heappop(target)

    if len(heap) < pool_size and fallback_heap:
        for entry in heapq.nlargest(pool_size - len(heap), fallback_heap):
            heapq.heappush(heap, entry)
            if len(heap) > pool_size:
                heapq.heappop(heap)

    return [entry[2] for entry in heapq.nlargest(pool_size, heap)]
