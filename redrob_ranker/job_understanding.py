"""Structured job understanding for the Senior AI Engineer JD."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

from .ontology import match_ontology


@dataclass(frozen=True)
class JobProfile:
    """Static job representation produced by the job-understanding agent."""

    role_title: str
    required_groups: dict[str, float]
    required_terms: set[str]
    nice_to_have_terms: set[str]
    disqualifier_terms: set[str]
    ideal_years_min: float = 5.0
    ideal_years_max: float = 9.0
    preferred_locations: set[str] = field(default_factory=set)
    raw_text: str = ""


DEFAULT_JD_TEXT = """
Senior AI Engineer Founding Team Redrob AI. Own ranking, retrieval, and matching systems
for recruiters. Needs production embeddings-based retrieval, vector databases or hybrid search,
strong Python, ranking evaluation frameworks such as NDCG, MRR, MAP, offline benchmarks and
A/B tests. Ideal profile has 6-8 years, applied ML or AI roles at product companies, shipped
end-to-end search, recommendation, ranking, matching, or retrieval systems to real users.
Avoid pure research without production, recent-only LangChain wrappers, senior leads who no
longer write code, pure services/consulting-only backgrounds, computer vision/speech/robotics
without NLP or information retrieval, and AI keyword stuffers with no career evidence.
Location Pune or Noida preferred; Hyderabad, Pune, Mumbai, Delhi NCR welcome; relocation helps.
"""


def default_job_profile(raw_text: str | None = None) -> JobProfile:
    """Return the final structured JD used by the offline pipeline."""

    text = raw_text or DEFAULT_JD_TEXT
    ontology = match_ontology([text])
    required_terms = {
        "embeddings",
        "retrieval",
        "vector",
        "hybrid",
        "search",
        "ranking",
        "recommendation",
        "matching",
        "python",
        "ndcg",
        "mrr",
        "map",
        "production",
        "product",
        "ml",
        "ai",
    }
    nice_to_have = {
        "lora",
        "qlora",
        "peft",
        "fine-tuning",
        "learning-to-rank",
        "xgboost",
        "distributed",
        "inference",
        "hr-tech",
        "open-source",
    }
    disqualifiers = {
        "marketing manager",
        "hr manager",
        "accountant",
        "sales executive",
        "graphic designer",
        "content writer",
        "customer support",
        "pure research",
        "consulting-only",
        "keyword stuffing",
    }
    return JobProfile(
        role_title="Senior AI Engineer - Founding Team",
        required_groups={
            "retrieval": 0.28,
            "ranking_eval": 0.27,
            "production_ml": 0.25,
            "core_engineering": 0.12,
            "llm_optional": 0.08,
        },
        required_terms=required_terms | ontology.canonical_skills,
        nice_to_have_terms=nice_to_have,
        disqualifier_terms=disqualifiers,
        preferred_locations={"pune", "noida", "hyderabad", "mumbai", "delhi", "gurgaon", "gurugram", "bangalore", "bengaluru"},
        raw_text=text,
    )


def extract_docx_text(path: str | Path) -> str:
    """Extract text from a DOCX file using only the standard library."""

    docx_path = Path(path)
    try:
        with zipfile.ZipFile(docx_path) as archive:
            xml = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Cannot read DOCX job description: {docx_path}") from exc

    root = ET.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for para in root.findall(".//w:p", namespace):
        pieces = [node.text or "" for node in para.findall(".//w:t", namespace)]
        if pieces:
            paragraphs.append("".join(pieces))
    return "\n".join(paragraphs)


def load_job_profile(path: str | Path | None = None) -> JobProfile:
    """Load and structure a JD, falling back to the reviewed static parse."""

    if path is None:
        return default_job_profile()
    text = extract_docx_text(path)
    return default_job_profile(text)
