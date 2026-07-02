"""Evidence-based explanation formatter."""

from __future__ import annotations

from .candidate import CandidateFacts
from .ranking import RankedCandidate
from .text import normalize_text


def _display_skill(skill: str, candidate: CandidateFacts) -> str:
    for item in candidate.skills:
        if item.canonical_name == skill or normalize_text(item.raw_name) == skill:
            return item.raw_name
    return skill.replace("_", " ")


def build_reasoning(row: RankedCandidate, max_chars: int = 420) -> str:
    """Generate a concise explanation from computed facts only."""

    candidate = row.candidate
    breakdown = row.breakdown
    matched = [_display_skill(skill, candidate) for skill in breakdown.matched_skills[:4]]
    skill_text = ", ".join(matched) if matched else "limited direct AI/retrieval skills"
    signals = candidate.redrob_signals
    response = float(signals.get("recruiter_response_rate", 0.0) or 0.0)
    notice = int(signals.get("notice_period_days", 0) or 0)
    active = "recently active" if (signals.get("open_to_work_flag") and breakdown.behavior >= 0.60) else "weaker availability signals"
    product_phrase = "product-company evidence" if breakdown.production_context >= 0.45 else "less product-company depth"
    first = (
        f"{candidate.current_title} with {candidate.years_of_experience:.1f} yrs; "
        f"matches the JD through {skill_text} and {product_phrase}."
    )
    second = (
        f"Behavior is {active}: response rate {response:.2f}, notice {notice} days, "
        f"confidence {breakdown.confidence:.2f}."
    )
    if breakdown.concerns:
        second += f" Concern: {breakdown.concerns[0]}."
    text = f"{first} {second}"
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
