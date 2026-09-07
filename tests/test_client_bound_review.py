"""Offline provenance contract; no production page evidence is synthesized."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_review_reconciler import prepared_review, server_review, EXPECTED_TARGET
import review_reconciler


def client_inputs():
    observed = server_review()
    observed.update(source="live_client_bound_form", server_saved=False,
        observed_at=datetime.now(timezone.utc).isoformat(),
        completeness={"verified": True, "unknown_controls": [], "invalid_controls": [], "gates": [],
                      "required_selectors": ["#first-name", "#school"]},
        bindings={field: {"bound": True, "valid": True, "visible": True, "enabled": True,
                          "count": 1} for field in observed["fields"]})
    observed["resume"].update(sha256="a" * 64, verified=True, attachment_present=True,
                               source="live_browser_file", content_type="application/pdf")
    return dict(preparation_evidence=prepared_review(), server_review=observed,
        expected_target=copy.deepcopy(EXPECTED_TARGET), profile_fields=copy.deepcopy(observed["fields"]),
        resume_preflight={"basename": "Resume.pdf", "sha256": "a" * 64,
                          "content_type": "application/pdf", "verified": True},
        required_parser_repairs=["#school"], required_question_ids=["work_authorization"])


def test_client_bound_review_is_explicitly_not_server_saved():
    result = review_reconciler.reconcile_review(**client_inputs())
    assert result["review_authoritative"] is True
    assert result.get("source") == "live_client_bound_form"
    assert result["server_saved"] is False
    assert result["submission_authorized"] is False
    assert "Fixture Person" not in json.dumps(result)


import pytest


@pytest.mark.parametrize("change", [
    lambda r: r.update(server_saved=True),
    lambda r: r.update(source="live_bound_form_state"),
    lambda r: r.update(observed_at="2000-01-01T00:00:00+00:00"),
    lambda r: r.update(observed_at="2999-01-01T00:00:00+00:00"),
    lambda r: r["bindings"]["#school"].update(bound=False),
    lambda r: r["completeness"].update(unknown_controls=["#new-question"]),
    lambda r: r["completeness"].update(gates=["captcha"]),
    lambda r: r["completeness"].update(required_selectors=["#missing"]),
    lambda r: r["resume"].update(sha256=""),
    lambda r: r["resume"].update(attachment_present=False),
])
def test_client_source_fails_closed_on_incomplete_unbound_stale_or_unattached_state(change):
    inputs = client_inputs()
    change(inputs["server_review"])
    assert review_reconciler.reconcile_review(**inputs)["review_authoritative"] is False


def test_client_hash_commits_to_values_and_choices_not_only_comparison_booleans():
    inputs = client_inputs()
    before = review_reconciler.reconcile_review(**inputs)
    inputs["server_review"]["fields"]["#first-name"] = "Changed Person"
    inputs["profile_fields"]["#first-name"] = "Changed Person"
    after = review_reconciler.reconcile_review(**inputs)
    assert before["review_evidence_sha256"] != after["review_evidence_sha256"]
    assert "Changed Person" not in json.dumps(after)


def test_client_source_rejects_unapproved_populated_optional_answer():
    inputs = client_inputs()
    inputs["server_review"]["fields"]["#unapproved"] = "unexpected answer"
    assert review_reconciler.reconcile_review(**inputs)["review_authoritative"] is False


@pytest.mark.parametrize("key", ["bindings", "completeness", "resume"])
def test_malformed_client_evidence_fails_closed_without_type_error(key):
    inputs = client_inputs()
    inputs["server_review"][key] = None
    with pytest.raises(review_reconciler.ReviewEvidenceError):
        review_reconciler.reconcile_review(**inputs)


@pytest.mark.parametrize('source', [None, 'server_saved_review'])
def test_exact_one_page_cannot_downgrade_to_legacy_server_provenance(source):
    from schonfeld_form import URL
    inputs=client_inputs()
    inputs['expected_target']['page_url']=URL
    inputs['preparation_evidence']['page_url']=URL
    inputs['server_review']['page_url']=URL
    if source is None: inputs['server_review'].pop('source')
    else: inputs['server_review'].update(source=source,server_saved=True)
    assert review_reconciler.reconcile_review(**inputs)['review_authoritative'] is False



