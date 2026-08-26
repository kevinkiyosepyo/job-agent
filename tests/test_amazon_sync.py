from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import amazon_sync


def test_build_tracker_row_marks_amazon_manual_only():
    job = {
        "company": "Amazon",
        "role": "Software Development Engineer Internship - Summer 2027 (US)",
        "url": "https://www.amazon.jobs/en/jobs/9999999/sde-intern",
        "location": "US, WA, Seattle",
        "posted_date": "August 26, 2026",
        "query": "summer 2027 software development engineer internship",
        "source_monitor": "sde",
    }

    row = amazon_sync.build_tracker_row(job)

    assert row["company"] == "Amazon"
    assert row["status"] == "Pending Manual Action"
    assert row["role"] == job["role"]
    assert row["url"] == job["url"]
    assert row["rejection"] == "N/A"
    assert "MAANGO manual-only" in row["notes"]
    assert "source_monitor=sde" in row["notes"]


def test_plan_sync_dedupes_jobs_and_skips_existing_tracker_duplicates():
    broad = [
        {
            "company": "Amazon",
            "role": "Product Manager Technical (PMT) Intern - Summer 2027",
            "url": "https://www.amazon.jobs/en/jobs/10509639/product-manager-technical-pmt-intern-summer-2027",
            "location": "US, WA, Seattle",
            "posted_date": "August 20, 2026",
            "query": "product manager intern",
            "source_monitor": "broad",
        }
    ]
    sde = [
        {
            "company": "Amazon",
            "role": "Software Development Engineer Internship - Summer 2027 (US)",
            "url": "https://www.amazon.jobs/en/jobs/3116030/software-development-engineer-internship-summer-2027-us",
            "location": "US, WA, Seattle",
            "posted_date": "August 26, 2026",
            "query": "summer 2027 software development engineer internship",
            "source_monitor": "sde",
        },
        {
            "company": "Amazon",
            "role": "Software Development Engineer Internship - Summer 2027 (US)",
            "url": "https://www.amazon.jobs/en/jobs/3116030/software-development-engineer-internship-summer-2027-us",
            "location": "US, WA, Seattle",
            "posted_date": "August 26, 2026",
            "query": "software engineer intern",
            "source_monitor": "sde",
        },
    ]

    def duplicate_checker(company: str, role: str, url: str) -> bool:
        return "10509639" in url

    plan = amazon_sync.plan_sync(broad_jobs=broad, sde_jobs=sde, duplicate_checker=duplicate_checker)

    assert [item["role"] for item in plan["to_append"]] == [
        "Software Development Engineer Internship - Summer 2027 (US)"
    ]
    assert plan["skipped_duplicates"][0]["role"] == "Product Manager Technical (PMT) Intern - Summer 2027"


def test_apply_plan_appends_tracker_rows_and_enqueues_discovered_jobs():
    plan = {
        "to_append": [
            {
                "company": "Amazon",
                "role": "Software Development Engineer Internship - Summer 2027 (US)",
                "url": "https://www.amazon.jobs/en/jobs/3116030/software-development-engineer-internship-summer-2027-us",
                "status": "Pending Manual Action",
                "salary": "",
                "date": "",
                "rejection": "N/A",
                "notes": "Amazon 2027 monitor. MAANGO manual-only.",
                "ats_platform": "Amazon.jobs",
            }
        ],
        "skipped_duplicates": [],
    }
    appended = []
    enqueued = []

    def append_row(row: dict) -> dict:
        appended.append(row)
        return {"status": "appended_verified", "values": row}

    def enqueue_job(*, company: str, role: str, url: str, ats_platform: str) -> dict:
        enqueued.append({
            "company": company,
            "role": role,
            "url": url,
            "ats_platform": ats_platform,
        })
        return {"id": 7, "state": "discovered"}

    result = amazon_sync.apply_plan(plan, append_row=append_row, enqueue_job=enqueue_job)

    assert len(appended) == 1
    assert len(enqueued) == 1
    assert result["appended_count"] == 1
    assert result["enqueued_count"] == 1
    assert enqueued[0]["ats_platform"] == "Amazon.jobs"
