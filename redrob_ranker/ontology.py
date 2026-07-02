"""Lightweight skill and role ontology for offline semantic expansion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .text import normalize_text, tokenize


CANONICAL_SKILLS: dict[str, set[str]] = {
    "python": {"python", "py"},
    "sql": {"sql", "postgres", "postgresql", "mysql", "snowflake", "warehouse"},
    "embeddings": {"embedding", "embeddings", "sentence-transformers", "bge", "e5", "sbert"},
    "semantic_search": {"semantic search", "vector search", "neural search", "similarity search"},
    "vector_database": {
        "faiss",
        "pinecone",
        "weaviate",
        "qdrant",
        "milvus",
        "opensearch",
        "elasticsearch",
        "lucene",
    },
    "hybrid_search": {"hybrid search", "bm25", "keyword search", "dense retrieval", "sparse retrieval"},
    "ranking": {
        "ranking",
        "ranker",
        "re-ranking",
        "reranking",
        "learning-to-rank",
        "ltr",
        "lambdamart",
        "xgboost",
    },
    "recommendations": {
        "recommendation",
        "recommendations",
        "recommender",
        "personalization",
        "matching",
        "candidate matching",
    },
    "evaluation": {"ndcg", "mrr", "map", "precision@k", "recall@k", "a/b", "ab test", "offline benchmark"},
    "llm": {"llm", "llms", "rag", "prompt", "fine-tuning", "finetuning", "lora", "qlora", "peft"},
    "nlp": {"nlp", "transformers", "bert", "roberta", "text classification", "information retrieval"},
    "mlops": {"mlops", "mlflow", "kubeflow", "model serving", "model monitoring", "bentoml", "wandb"},
    "data_engineering": {"spark", "pyspark", "airflow", "kafka", "flink", "databricks", "feature engineering"},
    "cloud_infra": {"aws", "gcp", "azure", "docker", "kubernetes", "k8s", "terraform"},
}

SKILL_GROUPS: dict[str, set[str]] = {
    "retrieval": {"embeddings", "semantic_search", "vector_database", "hybrid_search", "nlp"},
    "ranking_eval": {"ranking", "recommendations", "evaluation"},
    "production_ml": {"mlops", "cloud_infra", "data_engineering", "python"},
    "llm_optional": {"llm"},
    "core_engineering": {"python", "sql", "cloud_infra"},
}

TECHNICAL_TITLE_TERMS = {
    "engineer",
    "developer",
    "scientist",
    "architect",
    "ml",
    "ai",
    "data",
    "backend",
    "software",
    "search",
    "recommendation",
    "devops",
    "cloud",
}

NON_FIT_TITLE_TERMS = {
    "marketing",
    "hr",
    "accountant",
    "sales",
    "support",
    "writer",
    "designer",
    "mechanical",
    "civil",
}

SERVICE_COMPANIES = {
    "tcs",
    "infosys",
    "wipro",
    "accenture",
    "cognizant",
    "capgemini",
    "hcl",
    "tech mahindra",
    "mindtree",
    "mphasis",
}

PRODUCT_INDUSTRIES = {
    "software",
    "saas",
    "fintech",
    "e-commerce",
    "food delivery",
    "edtech",
    "ai/ml",
    "adtech",
    "healthtech",
    "healthtech ai",
    "conversational ai",
    "insurance tech",
    "gaming",
}

PREFERRED_LOCATIONS = {
    "pune",
    "noida",
    "delhi",
    "gurgaon",
    "gurugram",
    "mumbai",
    "hyderabad",
    "bangalore",
    "bengaluru",
}


@dataclass(frozen=True)
class OntologyMatch:
    """Canonical ontology evidence for a candidate or job text."""

    canonical_skills: set[str]
    groups: set[str]
    evidence: dict[str, set[str]]


def canonicalize_skill_name(name: str) -> str:
    """Map a raw skill to the closest canonical ontology key when known."""

    normalized = normalize_text(name).strip()
    for canonical, aliases in CANONICAL_SKILLS.items():
        if normalized == canonical or normalized in aliases:
            return canonical
    normalized_tokens = set(tokenize(normalized))
    for canonical, aliases in CANONICAL_SKILLS.items():
        for alias in aliases:
            alias_tokens = set(tokenize(alias))
            if alias_tokens and alias_tokens <= normalized_tokens:
                return canonical
    return normalized


def match_ontology(values: Iterable[str]) -> OntologyMatch:
    """Find canonical skill and group matches in free text or skill names."""

    canonical: set[str] = set()
    evidence: dict[str, set[str]] = {}
    texts = [normalize_text(v) for v in values if v]
    joined = "\n".join(texts)
    joined_tokens = set(tokenize(joined))

    for skill, aliases in CANONICAL_SKILLS.items():
        for alias in aliases | {skill}:
            alias_norm = normalize_text(alias)
            alias_tokens = set(tokenize(alias_norm))
            if not alias_tokens:
                continue
            if (" " in alias_norm and alias_norm in joined) or alias_tokens <= joined_tokens:
                canonical.add(skill)
                evidence.setdefault(skill, set()).add(alias)

    groups = {group for group, skills in SKILL_GROUPS.items() if canonical & skills}
    return OntologyMatch(canonical, groups, evidence)


def has_technical_title(title: str) -> bool:
    """Return true if a title has technical engineering/research signal."""

    tokens = set(tokenize(title))
    return bool(tokens & TECHNICAL_TITLE_TERMS)


def has_non_fit_title(title: str) -> bool:
    """Return true for titles the JD explicitly warns against."""

    tokens = set(tokenize(title))
    return bool(tokens & NON_FIT_TITLE_TERMS)


def is_service_company(company: str) -> bool:
    """Return true for service/consulting firms called out as poor fit."""

    return normalize_text(company).strip() in SERVICE_COMPANIES


def is_product_industry(industry: str) -> bool:
    """Return true for product/marketplace/software contexts."""

    return normalize_text(industry).strip() in PRODUCT_INDUSTRIES


def is_preferred_location(location: str) -> bool:
    """Return true for locations mentioned or implied by the JD logistics."""

    tokens = set(tokenize(location))
    return bool(tokens & PREFERRED_LOCATIONS)
