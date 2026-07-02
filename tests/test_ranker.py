import tempfile
import unittest
from pathlib import Path

from redrob_ranker.audit import audit_submission
from redrob_ranker.behavior import score_behavior
from redrob_ranker.candidate import iter_candidate_records, parse_candidate
from redrob_ranker.config import BehaviorWeights, RankerConfig
from redrob_ranker.job_understanding import default_job_profile
from redrob_ranker.ontology import canonicalize_skill_name
from redrob_ranker.ranking import RankedCandidate, ScoreBreakdown, score_skill_match
from redrob_ranker.submission import write_submission


def candidate_record(**overrides):
    record = {
        "candidate_id": "CAND_0000001",
        "profile": {
            "headline": "ML Engineer building vector search",
            "summary": "Built production retrieval and ranking systems for real users.",
            "location": "Pune",
            "country": "India",
            "years_of_experience": 7.0,
            "current_title": "Senior Machine Learning Engineer",
            "current_company": "Freshworks",
            "current_company_size": "1001-5000",
            "current_industry": "SaaS",
        },
        "career_history": [
            {
                "company": "Freshworks",
                "title": "Senior Machine Learning Engineer",
                "start_date": "2023-01-01",
                "end_date": None,
                "duration_months": 40,
                "is_current": True,
                "industry": "SaaS",
                "company_size": "1001-5000",
                "description": "Owned embeddings retrieval, hybrid search, ranking evaluation using NDCG and MRR.",
            }
        ],
        "education": [{"institution": "IIT", "degree": "M.Tech", "field_of_study": "Computer Science", "start_year": 2014, "end_year": 2016, "tier": "tier_1"}],
        "skills": [
            {"name": "Python", "proficiency": "expert", "endorsements": 25, "duration_months": 72},
            {"name": "FAISS", "proficiency": "advanced", "endorsements": 12, "duration_months": 30},
            {"name": "NDCG", "proficiency": "advanced", "endorsements": 5, "duration_months": 24},
        ],
        "certifications": [],
        "languages": [],
        "redrob_signals": {
            "profile_completeness_score": 92,
            "signup_date": "2025-01-01",
            "last_active_date": "2026-06-25",
            "open_to_work_flag": True,
            "profile_views_received_30d": 20,
            "applications_submitted_30d": 3,
            "recruiter_response_rate": 0.82,
            "avg_response_time_hours": 12,
            "skill_assessment_scores": {},
            "connection_count": 200,
            "endorsements_received": 20,
            "notice_period_days": 30,
            "expected_salary_range_inr_lpa": {"min": 20, "max": 35},
            "preferred_work_mode": "hybrid",
            "willing_to_relocate": True,
            "github_activity_score": 70,
            "search_appearance_30d": 100,
            "saved_by_recruiters_30d": 8,
            "interview_completion_rate": 0.9,
            "offer_acceptance_rate": 0.8,
            "verified_email": True,
            "verified_phone": True,
            "linkedin_connected": True,
        },
    }
    for key, value in overrides.items():
        record[key] = value
    return record


class RankerTests(unittest.TestCase):
    def test_skill_canonicalization(self):
        self.assertEqual(canonicalize_skill_name("FAISS"), "vector_database")
        self.assertEqual(canonicalize_skill_name("sentence-transformers"), "embeddings")

    def test_behavior_hard_filter_for_not_open(self):
        record = candidate_record()
        record["redrob_signals"]["open_to_work_flag"] = False
        candidate = parse_candidate(record)
        score = score_behavior(candidate, RankerConfig().evaluation_date, BehaviorWeights(), True)
        self.assertTrue(score.hard_filtered)
        self.assertLess(score.score, 0.8)

    def test_skill_match_uses_ontology(self):
        candidate = parse_candidate(candidate_record())
        skill_score, matched = score_skill_match(candidate, default_job_profile())
        self.assertGreater(skill_score, 0.35)
        self.assertIn("vector_database", matched)

    def test_submission_audit_accepts_known_candidate_id(self):
        candidate = parse_candidate(candidate_record())
        breakdown = ScoreBreakdown(
            skill_match=0.8,
            career_evidence=0.8,
            title_fit=0.8,
            ranking_evaluation=0.8,
            production_context=0.8,
            experience_range=0.8,
            logistics=0.8,
            education=0.8,
            open_source=0.8,
            behavior=0.8,
            trap_penalty=0.0,
            service_penalty=0.0,
            final_score=0.8,
            confidence=0.8,
            matched_skills=("vector_database",),
            concerns=(),
        )
        rows = [RankedCandidate(candidate=candidate, rank=1, score=0.8, breakdown=breakdown)]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            candidates_path = tmp_path / "candidates.jsonl"
            submission_path = tmp_path / "submission.csv"
            candidates_path.write_text(__import__("json").dumps(candidate_record()) + "\n", encoding="utf-8")
            write_submission(rows, submission_path, expected_rows=1, max_reasoning_chars=420)
            self.assertEqual(audit_submission(submission_path, candidates_path, expected_rows=1), [])

    def test_json_array_candidate_input_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.json"
            path.write_text(__import__("json").dumps([candidate_record()]), encoding="utf-8")
            records = list(iter_candidate_records(str(path)))
            self.assertEqual(records[0]["candidate_id"], "CAND_0000001")


if __name__ == "__main__":
    unittest.main()
