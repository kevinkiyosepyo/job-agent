"""Synthetic discovery-role examples prompted by the saved DRW pilot title."""
import scanner

PROFILE = {"preferences": {"target_roles": ["Software Engineer Intern"],
                            "target_levels": ["Intern"],
                            "location_preference": "United States"}}
JOB = {"company": "Example Research", "role": "Software Developer Intern",
       "url": "https://job-boards.greenhouse.io/example/jobs/1",
       "location": "United States"}


def test_software_developer_intern_matches_software_engineer_target():
    result = scanner.classify(JOB, PROFILE)
    assert "role:not_target_level" not in result["rejection_reasons"]
    assert result["role"] == JOB["role"]
    assert result["relevant"] is True


def test_developer_alias_preserves_role_and_level_exclusions():
    for role in ("Senior Software Developer Intern", "Software Developer",
                 "Business Developer Intern"):
        result = scanner.classify({**JOB, "role": role}, PROFILE)
        assert "role:not_target_level" in result["rejection_reasons"]
    other_profile = {"preferences": {"target_roles": ["Data Science Intern"]}}
    assert scanner.classify(JOB, other_profile)["relevant"] is False


def test_developer_alias_preserves_unknown_and_non_us_location_gates():
    unknown = scanner.classify({**JOB, "location": ""}, PROFILE)
    assert unknown["eligibility_status"] == "needs_verification"
    assert unknown["verification_reasons"] == ["location:needs_verification"]
    foreign = scanner.classify({**JOB, "location": "Toronto, Canada"}, PROFILE)
    assert foreign["rejection_reasons"] == ["location:not_us_or_remote"]


def test_developer_alias_does_not_clear_manual_or_duplicate_flags():
    result = scanner.classify({**JOB, "company": "Amazon"}, PROFILE,
                              known_urls=[JOB["url"]])
    assert result["manual_only"] is True
    assert result["maango_parent"] == "Amazon"
    assert result["duplicate"] is True
