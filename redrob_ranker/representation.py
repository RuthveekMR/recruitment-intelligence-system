"""Multi-vector candidate and job representations."""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter

from .candidate import CandidateFacts
from .job_understanding import JobProfile
from .text import tokenize


@dataclass(frozen=True)
class MultiVector:
    """Separate field vectors represented as token counters for late fusion."""

    summary: Counter[str]
    skills: Counter[str]
    experience: Counter[str]
    education: Counter[str]
    ontology: Counter[str]


def _counter_from_text(value: str) -> Counter[str]:
    return Counter(tokenize(value))


def candidate_vector(candidate: CandidateFacts) -> MultiVector:
    """Build a field-aware candidate representation."""

    return MultiVector(
        summary=_counter_from_text(f"{candidate.headline} {candidate.summary} {candidate.current_title}"),
        skills=Counter(skill.canonical_name for skill in candidate.skills if skill.canonical_name),
        experience=_counter_from_text(" ".join(f"{c.title} {c.industry} {c.description}" for c in candidate.careers)),
        education=_counter_from_text(" ".join(f"{e.get('degree', '')} {e.get('field_of_study', '')} {e.get('tier', '')}" for e in candidate.education)),
        ontology=Counter(candidate.canonical_skills | candidate.ontology_groups),
    )


def job_vector(job: JobProfile) -> MultiVector:
    """Build the matching representation for the structured JD."""

    group_terms = set(job.required_groups)
    return MultiVector(
        summary=_counter_from_text(job.raw_text),
        skills=Counter(job.required_terms | job.nice_to_have_terms),
        experience=_counter_from_text(job.raw_text),
        education=Counter({"computer": 1, "science": 1, "machine": 1, "learning": 1}),
        ontology=Counter(group_terms | job.required_terms),
    )


def weighted_overlap(left: Counter[str], right: Counter[str]) -> float:
    """Compute deterministic weighted overlap between sparse lexical vectors."""

    if not left or not right:
        return 0.0
    overlap = sum(min(left[token], right[token]) for token in right)
    target = sum(right.values())
    return overlap / target if target else 0.0
