from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prepare_live_job as live
import pytest


def test_conditional_required_control_reinventoried_after_filling():
    reads = []
    class Page:
        target_id = 'target'
        def read_only_snapshot(self):
            reads.append(1)
            return {'target_id': 'target', 'url': 'https://example.org/jobs/1',
                    'read_only': True, 'html': 'before' if len(reads) == 1 else 'after'}
    identity = {'company': 'Example', 'role': 'Software Intern', 'requisition': '1'}
    def prepare(**kwargs):
        return {**identity, 'platform': 'greenhouse', 'submission_enabled': False,
                'questions': [{'label': 'Unknown legal fact', 'required': True}] if kwargs['html_text'] == 'after' else []}
    result = live.prepare_live_job(page=Page(), target_id='target', expected_url='https://example.org/jobs/1',
        expected_identity=identity, profile={}, prepare=prepare,
        coverage=lambda **kw: {'known': [], 'human_required': kw['questions']},
        approved_answers={'first_name': 'Fixture'},
        apply_known=lambda _: {'verified': True, 'field_evidence': []})
    assert result['review_ready'] is False
    assert len(reads) == 2


def test_rendered_gate_blocks_before_any_form_mutation():
    identity = {'company': 'Example', 'role': 'Software Intern', 'requisition': '1'}
    class Page:
        target_id = 'target'
        def read_only_snapshot(self):
            return {'target_id':'target','url':'https://example.org/jobs/1', 'read_only':True,'html':'gate'}
    with pytest.raises(live.LivePreparationError, match='gate'):
        live.prepare_live_job(page=Page(), target_id='target', expected_url='https://example.org/jobs/1',
            expected_identity=identity, profile={},
            prepare=lambda **_: {**identity,'submission_enabled':False,'questions':[],'gates':['captcha']},
            coverage=lambda **_: {'human_required':[]}, approved_answers={'first_name':'Fixture'},
            apply_known=lambda _: pytest.fail('must not mutate behind a gate'))


def test_overlapping_control_ids_do_not_resolve_an_unanswered_question():
    coverage = {'known': [], 'human_required': [{'question': 'question_12'}]}
    evidence = {'field_evidence': [{'field': 'sponsorship', 'selector': '#question_1234', 'verified': True}]}
    assert live._resolve_verified_mapped_coverage(coverage, evidence)['human_required'] == [{'question': 'question_12'}]


def test_exact_escaped_control_id_can_resolve_its_own_question():
    coverage = {'known': [], 'human_required': [{'question': 'question[12]'}]}
    evidence = {'field_evidence': [{'field': 'sponsorship', 'selector': '#question\\[12\\]', 'verified': True}]}
    assert live._resolve_verified_mapped_coverage(coverage, evidence)['human_required'] == []
