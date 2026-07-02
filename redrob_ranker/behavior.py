"""Behavioral intelligence over Redrob signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import log1p
from typing import Any

from .candidate import CandidateFacts, parse_date
from .config import BehaviorWeights
from .text import clamp


@dataclass(frozen=True)
class BehaviorScore:
    """Transparent behavioral score and decision flags."""

    score: float
    hard_filtered: bool
    days_since_active: int | None
    reasons: tuple[str, ...]


def _number(signals: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(signals.get(key, default))
    except (TypeError, ValueError):
        return default


def score_behavior(candidate: CandidateFacts, today: date, weights: BehaviorWeights, hard_filter_open_to_work: bool) -> BehaviorScore:
    """Score Redrob activity, availability, and reliability signals."""

    signals = candidate.redrob_signals
    reasons: list[str] = []
    open_to_work = bool(signals.get("open_to_work_flag"))
    last_active = parse_date(signals.get("last_active_date"))
    days_since = (today - last_active).days if last_active else None
    recency = 0.0
    if days_since is not None:
        if days_since <= 14:
            recency = 1.0
        elif days_since <= 45:
            recency = 0.85
        elif days_since <= 90:
            recency = 0.65
        elif days_since <= 180:
            recency = 0.35
        else:
            recency = 0.08
    response_rate = clamp(_number(signals, "recruiter_response_rate"))
    avg_response_hours = _number(signals, "avg_response_time_hours", 240.0)
    response_speed = clamp(1.0 - avg_response_hours / 240.0)
    interview_completion = clamp(_number(signals, "interview_completion_rate"))
    offer_acceptance_raw = _number(signals, "offer_acceptance_rate", -1.0)
    offer_acceptance = 0.5 if offer_acceptance_raw < 0 else clamp(offer_acceptance_raw)
    profile_completeness = clamp(_number(signals, "profile_completeness_score") / 100.0)
    notice_period = int(_number(signals, "notice_period_days", 180.0))
    notice_score = 1.0 if notice_period <= 30 else 0.78 if notice_period <= 60 else 0.45 if notice_period <= 90 else 0.15
    relocation = 1.0 if bool(signals.get("willing_to_relocate")) else 0.45
    github = _number(signals, "github_activity_score", -1.0)
    github_score = 0.3 if github < 0 else clamp(github / 100.0)
    verification = sum(1 for key in ("verified_email", "verified_phone", "linkedin_connected") if signals.get(key)) / 3.0

    score = (
        weights.open_to_work * (1.0 if open_to_work else 0.0)
        + weights.recency * recency
        + weights.response_rate * response_rate
        + weights.response_speed * response_speed
        + weights.interview_completion * interview_completion
        + weights.offer_acceptance * offer_acceptance
        + weights.profile_completeness * profile_completeness
        + weights.notice_period * notice_score
        + weights.relocation * relocation
        + weights.github_activity * github_score
        + weights.verification * verification
    )
    total_weight = sum(weights.__dict__.values())
    score = clamp(score / total_weight if total_weight else 0.0)

    if not open_to_work:
        reasons.append("not marked open to work")
    if days_since is not None and days_since > 180:
        reasons.append(f"inactive for {days_since} days")
    if response_rate < 0.20:
        reasons.append(f"low recruiter response rate {response_rate:.2f}")
    if notice_period > 90:
        reasons.append(f"long notice period {notice_period} days")

    demand = log1p(_number(signals, "saved_by_recruiters_30d") + _number(signals, "profile_views_received_30d")) / 7.0
    score = clamp(score + min(0.04, demand * 0.02))
    hard_filtered = hard_filter_open_to_work and not open_to_work
    return BehaviorScore(score=score, hard_filtered=hard_filtered, days_since_active=days_since, reasons=tuple(reasons))
