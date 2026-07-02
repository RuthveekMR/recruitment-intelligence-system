"""Configuration for the offline Redrob ranking pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RankingWeights:
    """Transparent factor weights for deterministic ranking."""

    skill_match: float = 0.24
    career_evidence: float = 0.23
    title_fit: float = 0.13
    ranking_evaluation: float = 0.10
    production_context: float = 0.10
    experience_range: float = 0.08
    logistics: float = 0.05
    education: float = 0.03
    open_source: float = 0.04


@dataclass(frozen=True)
class BehaviorWeights:
    """Behavioral intelligence weights normalized to a 0..1 score."""

    open_to_work: float = 0.18
    recency: float = 0.18
    response_rate: float = 0.18
    response_speed: float = 0.08
    interview_completion: float = 0.10
    offer_acceptance: float = 0.05
    profile_completeness: float = 0.07
    notice_period: float = 0.06
    relocation: float = 0.04
    github_activity: float = 0.03
    verification: float = 0.03


@dataclass(frozen=True)
class RankerConfig:
    """Runtime configuration with conservative defaults for Stage 3 reproduction."""

    evaluation_date: date = date(2026, 7, 2)
    retrieval_pool_size: int = 2500
    output_rows: int = 100
    final_review_pool: int = 2500
    min_top_score: float = 0.0001
    hard_filter_open_to_work: bool = True
    max_reasoning_chars: int = 420
    ranking_weights: RankingWeights = field(default_factory=RankingWeights)
    behavior_weights: BehaviorWeights = field(default_factory=BehaviorWeights)

    @classmethod
    def from_json(cls, path: str | Path | None) -> "RankerConfig":
        """Load optional JSON overrides without introducing a YAML dependency."""

        if path is None:
            return cls()
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_mapping(raw)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "RankerConfig":
        """Create a config from a mapping of explicit overrides."""

        cfg = cls()
        simple_fields = {
            "retrieval_pool_size",
            "output_rows",
            "final_review_pool",
            "min_top_score",
            "hard_filter_open_to_work",
            "max_reasoning_chars",
        }
        updates: dict[str, Any] = {}
        for key in simple_fields:
            if key in data:
                updates[key] = data[key]
        if "evaluation_date" in data:
            updates["evaluation_date"] = date.fromisoformat(data["evaluation_date"])
        if "ranking_weights" in data:
            updates["ranking_weights"] = replace(cfg.ranking_weights, **data["ranking_weights"])
        if "behavior_weights" in data:
            updates["behavior_weights"] = replace(cfg.behavior_weights, **data["behavior_weights"])
        return replace(cfg, **updates)
