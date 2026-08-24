from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scanner


def make_profile() -> dict:
    return {
        "preferences": {
            "target_roles": ["Software Engineer Intern"],
            "target_timelines": ["Summer 2027"],
            "location_preference": "Remote or anywhere in U.S.",
        },
        "screening_defaults": {
            "authorized_to_work_us": True,
            "require_sponsorship": False,
        },
    }


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


def test_classify_rejects_non_us_location_with_explicit_reason(monkeypatch):
    monkeypatch.setattr(scanner, "tracker_duplicate", lambda company, role, url: False)

    result = scanner.classify(
        {
            "company": "Example",
            "role": "Software Engineer Intern",
            "url": "https://example.com/jobs/1",
            "location": "Toronto, Canada",
        },
        make_profile(),
    )

    assert result["relevant"] is False
    assert result["rejection_reasons"] == ["location:not_us_or_remote"]


def test_classify_rejects_non_target_season_with_explicit_reason(monkeypatch):
    monkeypatch.setattr(scanner, "tracker_duplicate", lambda company, role, url: False)

    result = scanner.classify(
        {
            "company": "Example",
            "role": "Software Engineer Intern, Winter 2027",
            "url": "https://example.com/jobs/2",
            "location": "Remote",
        },
        make_profile(),
    )

    assert result["relevant"] is False
    assert result["rejection_reasons"] == ["timeline:not_target"]


def test_classify_accepts_active_american_express_style_2027_title_without_explicit_season(monkeypatch):
    monkeypatch.setattr(scanner, "tracker_duplicate", lambda company, role, url: False)

    result = scanner.classify(
        {
            "company": "American Express",
            "role": "2027 Software Engineer, Technology - New York, NY",
            "url": "https://careers.americanexpress.com/en/sites/CX_1/job/26010970/",
            "location": "New York, NY",
            "season": "Campus Undergraduate Internship Program",
        },
        make_profile(),
    )

    assert result["relevant"] is True
    assert result["rejection_reasons"] == []


def test_classify_rejects_sponsorship_required_roles_with_explicit_reason(monkeypatch):
    monkeypatch.setattr(scanner, "tracker_duplicate", lambda company, role, url: False)

    result = scanner.classify(
        {
            "company": "Example",
            "role": "Software Engineer Intern, Summer 2027",
            "url": "https://example.com/jobs/3",
            "location": "Remote",
            "requires_sponsorship": True,
        },
        make_profile(),
    )

    assert result["relevant"] is False
    assert result["rejection_reasons"] == ["eligibility:sponsorship_required"]
