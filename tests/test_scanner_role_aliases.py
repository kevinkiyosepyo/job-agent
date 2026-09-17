"""Real applied-ledger titles the discovery matcher silently rejected.

Every role below is a confirmed submission in runtime/applied-ledger.json, so
the scanner must not classify it as ``role:not_target_level``. These are
regression cases, not synthetic spellings.
"""
import pytest
import scanner

PROFILE = {"preferences": {"target_roles": ["Software Engineer Intern", "Data Science Intern",
                                            "Data Analytics Intern", "Data Engineer Intern",
                                            "Product Management Intern", "Business Analyst Intern",
                                            "AI/ML Engineer Intern", "Quantitative Analyst Intern",
                                            "Research Intern"],
                           "target_levels": ["Intern", "Co-op", "New Grad", "Entry Level", "Fellow"],
                           "location_preference": "United States"}}
JOB = {"company": "Example Research", "url": "https://job-boards.greenhouse.io/example/jobs/1",
       "location": "United States"}

APPLIED_ROLES = [
    "Summer 2027 Internship - Software",
    "Software Support Engineer Internship (NetSuite) - Summer 2027",
    "Product Engineer Summer Internship",
    "Product Engineer Intern",
    "Internship: Forward Deployed Engineer, Software",
    "Fullstack Engineering Internship, Product Team",
    "Nearby AI Internship Program - Engineering Track",
    "2027 Guardian Summer Intern, Digital & Technology - AI & Machine Learning",
    "2027 Business Analytics Intern (NYC)",
    "Product Manager (HR Technology) Intern",
    "Associate Product Manager Intern",
]


@pytest.mark.parametrize("role", APPLIED_ROLES)
def test_confirmed_application_titles_are_not_rejected_as_off_target(role):
    result = scanner.classify({**JOB, "role": role}, PROFILE)
    assert result["rejection_reasons"] == []
    assert result["relevant"] is True


def test_seniority_exclusion_survives_the_product_manager_alias():
    for role in ("Senior Product Manager Intern", "Engineering Manager Intern",
                 "Lead Software Engineer Intern", "Director of Product Internship"):
        result = scanner.classify({**JOB, "role": role}, PROFILE)
        assert "role:not_target_level" in result["rejection_reasons"]


def test_bare_software_alias_does_not_match_non_engineering_functions():
    for role in ("Software Sales Intern", "Software Marketing Intern",
                 "Software Recruiting Intern"):
        result = scanner.classify({**JOB, "role": role}, PROFILE)
        assert "role:not_target_level" in result["rejection_reasons"]


def test_level_requirement_still_rejects_full_time_entry_titles():
    for role in ("Software Engineer I", "Product Engineer", "Business Analytics Associate"):
        result = scanner.classify({**JOB, "role": role}, PROFILE)
        assert "role:not_target_level" in result["rejection_reasons"]
