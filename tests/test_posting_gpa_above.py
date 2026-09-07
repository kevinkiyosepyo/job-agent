"""Synthetic reduced GPA wording observed in a public SWE pilot; not employer data."""
from posting_qualifications import qualification_decision


def test_explicit_gpa_of_or_above_clause_is_checked_against_canonical_gpa():
    result = qualification_decision({'content':'Requirements:\nGPA of 3.0 or above'}, {'education':{'gpa':3.2}})
    assert result['checks'] == [{'constraint':'gpa', 'verified':True}]
    assert result['status'] == 'qualified'


def test_gpa_boundary_never_infers_or_rounds_profile_fact():
    for value in [3.0, 4.0]:
        assert qualification_decision({'content':'GPA of 3.0 or above'}, {'education':{'gpa':value}})['status'] == 'qualified'
    for profile in [{}, {'education':{}}, *[{'education':{'gpa':value}} for value in [2.999, -1, 4.1, True, '3.2', None]]]:
        result = qualification_decision({'content':'GPA of 3.0 or above'}, profile)
        assert result['checks'] == [{'constraint':'gpa','verified':False}]
        assert result['status'] == 'blocked_fact'


def test_extra_mandatory_or_ambiguous_wording_still_blocks():
    for text in ['GPA of 3.0 or above and active clearance', 'GPA of 3.0 or above preferred',
                 'GPA of 3.0 or above\nHardware integration experience required',
                 'GPA of 4.5 or above', 'GPA of 3.0 or above on a 5-point scale']:
        result = qualification_decision({'content':text}, {'education':{'gpa':3.2}})
        assert result['status'] == 'blocked_fact'
        assert any(not item['verified'] for item in result['checks'])


def test_literal_escaped_clauses_remain_unsupported():
    result = qualification_decision({'content':'&lt;p&gt;GPA of 3.0 or above&lt;/p&gt;'}, {'education':{'gpa':3.2}})
    assert result['status'] == 'blocked_fact'


def test_unmet_gpa_parks_connected_backend_before_any_worker_request(tmp_path):
    from test_autonomous_backend import backend_with_candidate, FakeWorker
    from test_posting_qualifications import change_body
    from autonomous_controller import CandidateParked
    import pytest
    client = FakeWorker()
    backend, job = backend_with_candidate(tmp_path, client=client)
    change_body(backend, job, 'Requirements:\nGPA of 3.9 or above')
    with pytest.raises(CandidateParked):
        backend.prepare(job, lambda **_: None)
    assert client.requests == []
    assert not list(backend.root.glob('attempts/*/manifest.json'))
