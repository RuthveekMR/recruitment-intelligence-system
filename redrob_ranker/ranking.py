"""Deterministic final ranking engine."""

from __future__ import annotations

from dataclasses import dataclass
from math import log1p

from .candidate import CandidateFacts, latest_role_text
from .config import RankingWeights
from .job_understanding import JobProfile
from .ontology import (
    has_non_fit_title,
    has_technical_title,
    is_preferred_location,
    is_product_industry,
    is_service_company,
)
from .retrieval import RetrievedCandidate
from .text import clamp, normalize_text, tokenize


@dataclass(frozen=True)
class ScoreBreakdown:
    """Auditable score components for a ranked candidate."""

    skill_match: float
    career_evidence: float
    title_fit: float
    ranking_evaluation: float
    production_context: float
    experience_range: float
    logistics: float
    education: float
    open_source: float
    behavior: float
    trap_penalty: float
    service_penalty: float
    final_score: float
    confidence: float
    matched_skills: tuple[str, ...]
    concerns: tuple[str, ...]


@dataclass(frozen=True)
class RankedCandidate:
    """Final candidate ranking row with all evidence needed for explanations."""

    candidate: CandidateFacts
    rank: int
    score: float
    breakdown: ScoreBreakdown


def _skill_quality(skill_name: str, candidate: CandidateFacts) -> float:
    for skill in candidate.skills:
        if skill.canonical_name == skill_name or normalize_text(skill.raw_name) == skill_name:
            prof = {"beginner": 0.35, "intermediate": 0.60, "advanced": 0.82, "expert": 1.0}.get(skill.proficiency, 0.5)
            duration = clamp(skill.duration_months / 36.0)
            endorsements = clamp(log1p(skill.endorsements) / 4.2)
            return clamp(0.50 * prof + 0.30 * duration + 0.20 * endorsements)
    return 0.55 if skill_name in candidate.canonical_skills else 0.0


def score_skill_match(candidate: CandidateFacts, job: JobProfile) -> tuple[float, tuple[str, ...]]:
    """Score explicit skills plus ontology group coverage."""

    group_score = 0.0
    matched: set[str] = set()
    for group, weight in job.required_groups.items():
        group_skills = {
            "retrieval": {"embeddings", "semantic_search", "vector_database", "hybrid_search", "nlp"},
            "ranking_eval": {"ranking", "recommendations", "evaluation"},
            "production_ml": {"mlops", "cloud_infra", "data_engineering", "python"},
            "core_engineering": {"python", "sql", "cloud_infra"},
            "llm_optional": {"llm"},
        }[group]
        hits = group_skills & candidate.canonical_skills
        if hits:
            matched.update(hits)
            group_score += weight * clamp(sum(_skill_quality(hit, candidate) for hit in hits) / min(2.0, len(group_skills)))
    nice_hits = {term for term in job.nice_to_have_terms if term in candidate.text_tokens or term in candidate.canonical_skills}
    if nice_hits:
        matched.update(nice_hits)
    return clamp(group_score + min(0.08, len(nice_hits) * 0.015)), tuple(sorted(matched))


def score_career_evidence(candidate: CandidateFacts) -> float:
    """Score real career evidence for retrieval, ranking, ML systems, and shipping."""

    text = latest_role_text(candidate) + " " + normalize_text(candidate.profile_text)
    evidence_groups = [
        {"retrieval", "embedding", "vector", "semantic", "search", "faiss", "milvus", "qdrant", "elasticsearch"},
        {"ranking", "recommendation", "recommender", "matching", "personalization"},
        {"production", "deployed", "scale", "users", "pipeline", "serving", "monitoring", "on-call"},
        {"evaluation", "ndcg", "mrr", "map", "benchmark", "a/b", "ab", "experiment"},
        {"python", "spark", "ml", "ai", "nlp", "feature"},
    ]
    tokens = set(tokenize(text))
    score = 0.0
    for group in evidence_groups:
        if tokens & group:
            score += 0.20
    senior_shipping = {"owned", "led", "designed", "built", "shipped", "architected"} & tokens
    if senior_shipping:
        score += 0.10
    return clamp(score)


def score_title_fit(candidate: CandidateFacts) -> float:
    """Score role-title alignment while defending against keyword stuffers."""

    title = candidate.current_title
    title_norm = normalize_text(title)
    if any(term in title_norm for term in ("recommendation", "search", "ranking")):
        return 1.0
    if "senior" in title_norm and any(term in title_norm for term in ("machine learning", "software", "data", "ai")):
        return 0.92
    if any(term in title_norm for term in ("ml engineer", "ai engineer", "data scientist", "machine learning engineer")):
        return 0.88
    if any(term in title_norm for term in ("data engineer", "backend engineer", "software engineer", "cloud engineer", "devops engineer")):
        return 0.72
    if has_technical_title(title):
        return 0.52
    if has_non_fit_title(title):
        return 0.04
    return 0.20


def score_experience_range(candidate: CandidateFacts, job: JobProfile) -> float:
    """Score years of experience against the JD's flexible 5-9 year target."""

    years = candidate.years_of_experience
    if 6.0 <= years <= 8.5:
        return 1.0
    if job.ideal_years_min <= years <= job.ideal_years_max:
        return 0.90
    if 4.0 <= years < job.ideal_years_min:
        return 0.65 + 0.20 * ((years - 4.0) / 1.0)
    if job.ideal_years_max < years <= 11.0:
        return 0.78
    if 3.0 <= years < 4.0 or 11.0 < years <= 13.0:
        return 0.35
    return 0.10


def score_production_context(candidate: CandidateFacts) -> tuple[float, float]:
    """Score product-company exposure and service-only penalty."""

    product_months = 0
    service_months = 0
    total_months = 0
    for career in candidate.careers:
        total_months += career.duration_months
        if is_product_industry(career.industry) and not is_service_company(career.company):
            product_months += career.duration_months
        if is_service_company(career.company):
            service_months += career.duration_months
    current_bonus = 0.15 if is_product_industry(candidate.current_industry) and not is_service_company(candidate.current_company) else 0.0
    product_score = clamp((product_months / max(total_months, 1)) + current_bonus)
    service_ratio = service_months / max(total_months, 1)
    service_penalty = 0.12 if service_ratio > 0.92 else 0.06 if service_ratio > 0.70 else 0.0
    return product_score, service_penalty


def score_logistics(candidate: CandidateFacts) -> float:
    """Score India/location/work-mode and relocation practicality."""

    signals = candidate.redrob_signals
    country_score = 0.45 if normalize_text(candidate.country) == "india" else 0.10
    location_score = 0.30 if is_preferred_location(candidate.location) else 0.0
    relocate_score = 0.18 if signals.get("willing_to_relocate") else 0.02
    mode = normalize_text(signals.get("preferred_work_mode", ""))
    mode_score = 0.07 if mode in {"hybrid", "flexible", "onsite"} else 0.02
    return clamp(country_score + location_score + relocate_score + mode_score)


def score_education(candidate: CandidateFacts) -> float:
    """Use education as a capped secondary signal."""

    best = 0.0
    for edu in candidate.education:
        field = normalize_text(edu.get("field_of_study", ""))
        degree = normalize_text(edu.get("degree", ""))
        tier = normalize_text(edu.get("tier", ""))
        relevance = 0.45 if any(term in field for term in ("computer", "information", "machine", "data", "statistics", "mathematics")) else 0.15
        level = 0.35 if any(term in degree for term in ("m.tech", "m.e", "m.sc", "master", "ph.d", "phd")) else 0.20
        prestige = {"tier_1": 0.20, "tier_2": 0.14, "tier_3": 0.07, "tier_4": 0.02}.get(tier, 0.04)
        best = max(best, relevance + level + prestige)
    return clamp(best)


def score_open_source(candidate: CandidateFacts) -> float:
    """Score external validation from GitHub and public-ish profile signals."""

    github = float(candidate.redrob_signals.get("github_activity_score", -1) or -1)
    if github < 0:
        github_score = 0.15
    else:
        github_score = clamp(github / 100.0)
    endorsements = clamp(log1p(float(candidate.redrob_signals.get("endorsements_received", 0) or 0)) / 5.0)
    return clamp(0.75 * github_score + 0.25 * endorsements)


def trap_penalty(candidate: CandidateFacts, skill_match: float, career_evidence: float, title_fit: float) -> tuple[float, tuple[str, ...]]:
    """Detect likely honeypot or keyword-stuffed candidates without special IDs."""

    concerns: list[str] = []
    penalty = 0.0
    ai_skill_count = len(candidate.canonical_skills & {"embeddings", "semantic_search", "vector_database", "hybrid_search", "ranking", "recommendations", "llm", "nlp"})
    if ai_skill_count >= 5 and title_fit < 0.20 and career_evidence < 0.35:
        penalty += 0.24
        concerns.append("AI skills look disconnected from current role evidence")
    suspicious_skills = [
        skill
        for skill in candidate.skills
        if skill.proficiency in {"advanced", "expert"} and skill.duration_months <= 3
    ]
    if len(suspicious_skills) >= 4:
        penalty += 0.18
        concerns.append("multiple advanced skills have very low duration evidence")
    if len(candidate.skills) >= 18 and career_evidence < 0.35:
        penalty += 0.10
        concerns.append("large skill list with limited career evidence")
    if skill_match > 0.65 and career_evidence < 0.25:
        penalty += 0.12
        concerns.append("profile relies more on skills list than shipped-system evidence")
    return clamp(penalty, 0.0, 0.45), tuple(concerns)


def score_candidate(item: RetrievedCandidate, job: JobProfile, weights: RankingWeights) -> ScoreBreakdown:
    """Compute the transparent deterministic final score."""

    candidate = item.candidate
    skill_match, matched_skills = score_skill_match(candidate, job)
    career = score_career_evidence(candidate)
    title = score_title_fit(candidate)
    ranking_eval = 1.0 if (candidate.canonical_skills & {"ranking", "recommendations", "evaluation"}) else clamp(career * 0.75)
    production, service_penalty = score_production_context(candidate)
    experience = score_experience_range(candidate, job)
    logistics = score_logistics(candidate)
    education = score_education(candidate)
    open_source = score_open_source(candidate)
    trap, concerns = trap_penalty(candidate, skill_match, career, title)

    base = (
        weights.skill_match * skill_match
        + weights.career_evidence * career
        + weights.title_fit * title
        + weights.ranking_evaluation * ranking_eval
        + weights.production_context * production
        + weights.experience_range * experience
        + weights.logistics * logistics
        + weights.education * education
        + weights.open_source * open_source
    )
    behavior = item.behavior.score
    behavior_modifier = 0.62 + 0.48 * behavior
    hard_penalty = 0.42 if item.behavior.hard_filtered else 0.0
    final = clamp(0.84 * base * behavior_modifier + 0.04 * item.retrieval_score - trap - service_penalty - hard_penalty)
    evidence_completeness = sum(1 for value in (skill_match, career, title, ranking_eval, production, behavior) if value >= 0.55) / 6.0
    confidence = clamp(0.55 * evidence_completeness + 0.30 * behavior + 0.15 * (1.0 - trap))
    all_concerns = tuple(list(concerns) + list(item.behavior.reasons))
    return ScoreBreakdown(
        skill_match=skill_match,
        career_evidence=career,
        title_fit=title,
        ranking_evaluation=ranking_eval,
        production_context=production,
        experience_range=experience,
        logistics=logistics,
        education=education,
        open_source=open_source,
        behavior=behavior,
        trap_penalty=trap,
        service_penalty=service_penalty + hard_penalty,
        final_score=final,
        confidence=confidence,
        matched_skills=matched_skills,
        concerns=all_concerns,
    )


def rank_retrieved(items: list[RetrievedCandidate], job: JobProfile, weights: RankingWeights, limit: int) -> list[RankedCandidate]:
    """Score and sort retrieved candidates with deterministic tie-breakers."""

    scored = [(item, score_candidate(item, job, weights)) for item in items]
    scored.sort(
        key=lambda pair: (
            -pair[1].final_score,
            -pair[1].skill_match,
            -pair[1].career_evidence,
            -pair[1].behavior,
            abs(pair[0].candidate.years_of_experience - 7.0),
            pair[0].candidate.candidate_id,
        )
    )
    output: list[RankedCandidate] = []
    previous_score: float | None = None
    for index, (item, breakdown) in enumerate(scored[:limit], 1):
        score = round(breakdown.final_score, 6)
        if previous_score is not None and score >= previous_score:
            score = max(previous_score - 0.000001, 0.0)
        previous_score = score
        output.append(RankedCandidate(candidate=item.candidate, rank=index, score=score, breakdown=breakdown))
    return output
