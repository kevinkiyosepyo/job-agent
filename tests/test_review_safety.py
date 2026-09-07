"""Offline safety regressions; evidence fixtures are not live authority."""
import copy
import json

import pytest

from test_review_reconciler import EXPECTED_TARGET, prepared_review, server_review
from review_reconciler import reconcile_review


def inputs() -> dict:
    rendered = server_review()
    rendered['resume']['sha256'] = 'a' * 64
    return dict(preparation_evidence=prepared_review(), server_review=rendered,
                expected_target=copy.deepcopy(EXPECTED_TARGET),
                profile_fields=copy.deepcopy(rendered['fields']),
                resume_preflight={'basename': 'Resume.pdf', 'sha256': 'a' * 64,
                                  'verified': True, 'content_type': 'application/pdf'},
                required_parser_repairs=['#school'], required_question_ids=['work_authorization'])


@pytest.mark.parametrize('source', [None, '', 'dom_visible', 'server_saved_review'])
def test_review_requires_explicit_consistent_provenance(source):
    args = inputs()
    if source is None:
        args['server_review'].pop('source')
    else:
        args['server_review']['source'] = source
    if source == 'server_saved_review':
        args['server_review']['server_saved'] = False
    result = reconcile_review(**args)
    assert result['review_authoritative'] is False
    assert any(item['type'] == 'unknown_review_source' for item in result['human_required'])


@pytest.mark.parametrize('digest', [None, '', 'not-a-digest', 'b' * 64, 'z' * 64])
def test_actual_uploaded_bytes_must_match_resume_preflight(digest):
    args = inputs()
    args['server_review']['resume'].update(sha256=digest, verified=True)
    if digest in ('not-a-digest', 'z' * 64):
        args['resume_preflight']['sha256'] = digest
    result = reconcile_review(**args)
    assert result['resume']['verified'] is False
    assert result['review_authoritative'] is False


@pytest.mark.parametrize('changed', ['field', 'option', 'profile', 'resume'])
def test_generic_hash_commits_to_actual_private_content(changed):
    args = inputs()
    args['server_review']['bindings'] = {'#school': {'choice': [{'value': 'school-1', 'label': 'Fixture University'}]}}
    before = reconcile_review(**args)
    assert before['review_authoritative'] is True
    if changed == 'field':
        args['server_review']['fields']['#first-name'] = 'Different Person'
        args['profile_fields']['#first-name'] = 'Different Person'
    elif changed == 'option':
        args['server_review']['bindings']['#school']['choice'][0]['value'] = 'school-2'
    elif changed == 'profile':
        # Both remain mismatches; comparison booleans must not determine the hash.
        args['profile_fields']['#first-name'] = 'First Expected'
        before = reconcile_review(**args)
        args['profile_fields']['#first-name'] = 'Second Expected'
    else:
        args['resume_preflight']['sha256'] = 'b' * 64
        args['server_review']['resume']['sha256'] = 'b' * 64
    after = reconcile_review(**args)
    assert before['fields'] == after['fields']
    assert before['resume'] == after['resume']
    assert before['review_evidence_sha256'] != after['review_evidence_sha256']
    assert not any(value in json.dumps(after) for value in ['Different Person', 'school-2', 'Second Expected', 'b' * 64])


def test_generic_review_rejects_unapproved_prefilled_material_fact():
    args = inputs()
    args['preparation_evidence']['applied_answers']['field_evidence'] = []
    args['server_review']['fields']['#gpa'] = '3.8'
    result = reconcile_review(**args)
    assert result['review_authoritative'] is False
    assert any(item['type'] == 'unknown_profile_fact' for item in result['human_required'])


@pytest.mark.parametrize('value', [None, '', [], {}])
def test_unknown_canonical_material_fact_cannot_self_match(value):
    args = inputs()
    args['profile_fields']['#school'] = value
    args['server_review']['fields']['#school'] = value
    result = reconcile_review(**args)
    assert result['review_authoritative'] is False


def test_prefilled_gpa_is_validated_independently_without_answer_actions():
    from canonical_answers import canonical_review_fields
    from test_canonical_answers import profile, controls
    args = inputs()
    args['profile_fields'] = canonical_review_fields(profile(), controls())
    args['server_review']['fields'] = {'#gpa': '3.236', '#auth': 'Yes'}
    args['required_parser_repairs'] = []
    args['required_question_ids'] = []
    args['server_review']['questions'] = []
    args['preparation_evidence']['applied_answers']['field_evidence'] = []
    assert reconcile_review(**args)['review_authoritative'] is True
    args['server_review']['fields']['#gpa'] = '3.8'
    assert reconcile_review(**args)['review_authoritative'] is False


@pytest.mark.parametrize('required', [True, False])
def test_question_flags_alone_never_ground_unknown_material_answers(required):
    args = inputs()
    args['server_review']['questions'].append({'id': 'security_clearance', 'required': required,
        'answered': True, 'verified': True, 'answer': 'Yes'})
    assert reconcile_review(**args)['review_authoritative'] is False


@pytest.mark.parametrize('change', [
    lambda a: a['server_review']['questions'][0].update(answer='No'),
    lambda a: a['server_review']['questions'].append(dict(a['server_review']['questions'][0])),
    lambda a: a['server_review']['questions'].append({'required': True, 'answered': True, 'verified': True}),
])
def test_question_evidence_must_be_unambiguous_and_consistent_with_canonical_field(change):
    args = inputs()
    change(args)
    assert reconcile_review(**args)['review_authoritative'] is False


def test_empty_expected_and_observed_review_cannot_pass_vacuously():
    args = inputs()
    args.update(profile_fields={}, required_question_ids=[], required_parser_repairs=[])
    args['server_review'].update(fields={}, questions=[])
    assert reconcile_review(**args)['review_authoritative'] is False


def test_review_hash_is_stable_for_dictionary_order_not_fresh_observation_time():
    args = inputs()
    before = reconcile_review(**args)
    args['profile_fields'] = dict(reversed(list(args['profile_fields'].items())))
    args['server_review']['fields'] = dict(reversed(list(args['server_review']['fields'].items())))
    args['server_review']['observed_at'] = '2026-09-05T00:00:00+00:00'
    assert reconcile_review(**args)['review_evidence_sha256'] == before['review_evidence_sha256']


def test_profile_digest_drift_changes_review_commitment_even_if_relevant_values_agree():
    args = inputs()
    args['preparation_evidence']['evidence']['input_binding'] = {'profile_sha256': 'c' * 64}
    before = reconcile_review(**args)
    args['preparation_evidence']['evidence']['input_binding']['profile_sha256'] = 'd' * 64
    assert reconcile_review(**args)['review_evidence_sha256'] != before['review_evidence_sha256']
