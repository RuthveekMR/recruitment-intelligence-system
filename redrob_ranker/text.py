"""Text normalization utilities used across parsing and retrieval."""

from __future__ import annotations

import re
from typing import Iterable

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9.+#/-]*")


def normalize_text(value: object) -> str:
    """Return a lowercase ASCII-ish text representation for matching."""

    if value is None:
        return ""
    text = str(value).lower()
    return (
        text.replace("–", "-")
        .replace("—", "-")
        .replace("’", "'")
        .replace("&", " and ")
    )


def tokenize(value: object) -> list[str]:
    """Tokenize text deterministically for lexical and ontology matching."""

    return TOKEN_RE.findall(normalize_text(value))


def token_set(values: Iterable[object]) -> set[str]:
    """Tokenize multiple values into a set."""

    out: set[str] = set()
    for value in values:
        out.update(tokenize(value))
    return out


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp a numeric score into an inclusive range."""

    return max(low, min(high, value))


def ratio(numerator: float, denominator: float) -> float:
    """Safe ratio helper."""

    if denominator <= 0:
        return 0.0
    return numerator / denominator
