"""Synthetic role spelling cases prompted by the saved Virtu UI internship."""
import pytest
import scanner

PROFILE = {"preferences": {"target_roles": ["Software Engineer Intern"],
                            "target_levels": ["Intern"],
                            "location_preference": "United States"}}
JOB = {"company": "Example Research", "url": "https://example.com/jobs/1",
       "location": "United States"}


@pytest.mark.parametrize("role", ["2027 Internship - Frontend Engineer (UI)",
                                  "Front-End Engineer Intern",
                                  "Front End Engineer Internship"])
def test_frontend_engineering_internship_matches_software_target(role):
    result = scanner.classify({**JOB, "role": role}, PROFILE)
    assert result["rejection_reasons"] == []
    assert result["relevant"] is True
    assert result["role"] == role


def test_frontend_alias_preserves_role_level_exclusions():
    for role in ("Frontend Designer Intern", "Senior Frontend Engineer Intern", "Frontend Engineer"):
        result = scanner.classify({**JOB, "role": role}, PROFILE)
        assert "role:not_target_level" in result["rejection_reasons"]


def test_frontend_alias_requires_the_software_target():
    profile = {"preferences": {**PROFILE["preferences"], "target_roles": ["Data Scientist Intern"]}}
    result = scanner.classify({**JOB, "role": "Frontend Engineer Intern"}, profile)
    assert "role:not_target_level" in result["rejection_reasons"]


def test_frontend_alias_preserves_geography_and_manual_gate():
    role = "Frontend Engineer Intern"
    non_us = scanner.classify({**JOB, "role": role, "location": "Toronto, Canada"}, PROFILE)
    assert "location:not_us_or_remote" in non_us["rejection_reasons"]
    manual = scanner.classify({**JOB, "role": role, "company": "Amazon"}, PROFILE)
    assert manual["manual_only"] is True
