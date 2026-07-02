"""Candidate parsing and normalized fact extraction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from typing import Any, Iterable, Iterator

from .ontology import canonicalize_skill_name, match_ontology
from .text import normalize_text, token_set


@dataclass(frozen=True)
class SkillFact:
    """Normalized skill fact with original evidence."""

    raw_name: str
    canonical_name: str
    proficiency: str
    endorsements: int
    duration_months: int


@dataclass(frozen=True)
class CareerFact:
    """Normalized career entry."""

    company: str
    title: str
    industry: str
    company_size: str
    duration_months: int
    is_current: bool
    description: str


@dataclass(frozen=True)
class CandidateFacts:
    """Normalized candidate profile used by representation and scoring agents."""

    candidate_id: str
    headline: str
    summary: str
    location: str
    country: str
    years_of_experience: float
    current_title: str
    current_company: str
    current_company_size: str
    current_industry: str
    careers: tuple[CareerFact, ...]
    skills: tuple[SkillFact, ...]
    education: tuple[dict[str, Any], ...]
    certifications: tuple[dict[str, Any], ...]
    redrob_signals: dict[str, Any]
    text_tokens: set[str]
    canonical_skills: set[str]
    ontology_groups: set[str]

    @property
    def profile_text(self) -> str:
        """Textual profile fields for retrieval and explanation."""

        career_text = " ".join(f"{c.title} {c.company} {c.industry} {c.description}" for c in self.careers)
        skill_text = " ".join(skill.raw_name for skill in self.skills)
        cert_text = " ".join(str(cert.get("name", "")) for cert in self.certifications)
        return " ".join([self.headline, self.summary, self.current_title, self.current_industry, career_text, skill_text, cert_text])


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_candidate(record: dict[str, Any]) -> CandidateFacts:
    """Parse a raw JSON candidate into deterministic normalized facts."""

    profile = record.get("profile") or {}
    raw_skills = record.get("skills") or []
    skills = tuple(
        SkillFact(
            raw_name=str(skill.get("name", "")),
            canonical_name=canonicalize_skill_name(str(skill.get("name", ""))),
            proficiency=str(skill.get("proficiency", "")),
            endorsements=_parse_int(skill.get("endorsements")),
            duration_months=_parse_int(skill.get("duration_months")),
        )
        for skill in raw_skills
    )
    careers = tuple(
        CareerFact(
            company=str(career.get("company", "")),
            title=str(career.get("title", "")),
            industry=str(career.get("industry", "")),
            company_size=str(career.get("company_size", "")),
            duration_months=_parse_int(career.get("duration_months")),
            is_current=bool(career.get("is_current")),
            description=str(career.get("description", "")),
        )
        for career in (record.get("career_history") or [])
    )
    text_values: list[str] = [
        str(profile.get("headline", "")),
        str(profile.get("summary", "")),
        str(profile.get("current_title", "")),
        str(profile.get("current_industry", "")),
    ]
    text_values.extend(f"{career.title} {career.company} {career.industry} {career.description}" for career in careers)
    text_values.extend(skill.raw_name for skill in skills)
    text_values.extend(str(cert.get("name", "")) for cert in (record.get("certifications") or []))
    ontology = match_ontology(text_values)
    canonical_skills = {skill.canonical_name for skill in skills if skill.canonical_name}
    canonical_skills |= ontology.canonical_skills
    return CandidateFacts(
        candidate_id=str(record.get("candidate_id", "")),
        headline=str(profile.get("headline", "")),
        summary=str(profile.get("summary", "")),
        location=str(profile.get("location", "")),
        country=str(profile.get("country", "")),
        years_of_experience=_parse_float(profile.get("years_of_experience")),
        current_title=str(profile.get("current_title", "")),
        current_company=str(profile.get("current_company", "")),
        current_company_size=str(profile.get("current_company_size", "")),
        current_industry=str(profile.get("current_industry", "")),
        careers=careers,
        skills=skills,
        education=tuple(record.get("education") or []),
        certifications=tuple(record.get("certifications") or []),
        redrob_signals=dict(record.get("redrob_signals") or {}),
        text_tokens=token_set(text_values),
        canonical_skills=canonical_skills,
        ontology_groups=ontology.groups,
    )


def iter_candidate_records(path: str) -> Iterator[dict[str, Any]]:
    """Stream raw candidate JSON objects from JSONL or a JSON sample array."""

    source = Path(path)
    if source.suffix.lower() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            for record in payload:
                if isinstance(record, dict):
                    yield record
                else:
                    raise ValueError(f"Expected object records in {path}")
            return
        if isinstance(payload, dict):
            yield payload
            return
        raise ValueError(f"Expected JSON object or array in {path}")

    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc


def iter_candidates(path: str) -> Iterator[CandidateFacts]:
    """Stream parsed candidate facts from JSONL."""

    for record in iter_candidate_records(path):
        yield parse_candidate(record)


def latest_role_text(candidate: CandidateFacts) -> str:
    """Return a compact description of current work for reasoning."""

    current = next((career for career in candidate.careers if career.is_current), None)
    if current is None and candidate.careers:
        current = candidate.careers[0]
    if current is None:
        return ""
    return normalize_text(f"{current.title} {current.industry} {current.description}")


def parse_date(value: object) -> date | None:
    """Parse ISO dates from Redrob signals, returning None on malformed data."""

    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
