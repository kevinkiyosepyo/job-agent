from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scanner


def test_maango_word_match_avoids_apple_federal_credit_union_false_positive():
    assert scanner.maango_company("Apple Federal Credit Union", "https://www.applefcu.org/jobs") is None


def test_maango_domain_identifies_linkedin_as_microsoft():
    assert scanner.maango_company("LinkedIn", "https://www.linkedin.com/jobs/view/1") == "Microsoft"


def test_detects_greenhouse_and_workday():
    assert scanner.detect_ats("https://job-boards.greenhouse.io/example/jobs/1") == "Greenhouse"
    assert scanner.detect_ats("https://example.wd1.myworkdayjobs.com/job/1") == "Workday"


def test_relevant_accepts_machine_learning_variant():
    profile = {"preferences": {"target_roles": ["AI/ML Engineer Intern"]}}
    assert scanner.relevant("Machine Learning Engineer Intern", profile)


def test_relevant_rejects_senior_intern_manager_noise():
    profile = {"preferences": {"target_roles": ["Software Engineer Intern"]}}
    assert not scanner.relevant("Senior Software Engineer Intern Manager", profile)


def test_unique_jobs_prefers_first_exact_normalized_url():
    jobs = [
        {"company": "A", "role": "Software Engineer Intern", "url": "https://example.com/1?utm_source=x"},
        {"company": "A", "role": "Software Engineer Intern", "url": "https://example.com/1/"},
    ]
    assert scanner.unique_jobs(jobs) == [jobs[0]]
