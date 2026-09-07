"""Synthetic reduced section/GPA structure observed in the public SpaceX pilot."""
from posting_qualifications import qualification_decision
import pytest


@pytest.mark.parametrize('intervening', [
    'Requirements:', 'Qualifications:', 'Required Qualifications:',
    'Additional Requirements:', 'Unrecognized prose',
    'U.S. citizenship required', 'GPA of 3.0 or above',
])
def test_preferred_scope_expires_after_one_nonempty_clause(intervening):
    result = qualification_decision({'content':
        'Minimum GPA of 3.0\nPreferred Qualifications:\n'+intervening+'\nGPA of 3.5 or above'},
        {'education':{'gpa':3.2},'citizenship':'United States'})
    assert result['status'] == 'blocked_fact'
    assert result['checks'][-1] == {'constraint':'gpa','verified':False}


@pytest.mark.parametrize('body', [
    'Preferred Qualifications:\nGPA of 3.5 or above',
    'Minimum GPA of 3.5\nPreferred Qualifications:\nGPA of 3.0 or above',
    'Minimum GPA of 3.0\nPreferred Qualifications:\nGPA of 3.5 or above\nSecurity clearance required',
    'Minimum GPA of 3.0\nPreferred Qualifications:\nGPA of 3.5 or above and active clearance',
    'Minimum GPA of 3.0\nPreferred Qualifications:\nGPA of 3.5 or above on a 5-point scale',
    'Minimum GPA of 3.0\nPreferred Qualifications or Requirements:\nGPA of 3.5 or above',
    'Minimum GPA of 3.0\nPreferred Qualifications:\nRequired skills: Rust',
    '&lt;p&gt;Minimum GPA of 3.0&lt;/p&gt;&lt;h3&gt;Preferred Qualifications:&lt;/h3&gt;&lt;p&gt;GPA of 3.5 or above&lt;/p&gt;',
])
def test_other_unsupported_or_unmet_required_content_still_blocks(body):
    result = qualification_decision({'content':body}, {'education':{'gpa':3.2}})
    assert result['status'] == 'blocked_fact'


@pytest.mark.parametrize('gpa,verified', [(3.5,True),(4.0,True),(3.2,False),('3.5',False),(True,False),(None,False)])
def test_html_preferred_clause_retains_honest_fact_result_and_commitments(gpa, verified):
    from posting_qualifications import content_hash
    posting = {'content':'<h3>Requirements:</h3><p>U.S. citizenship required</p>'
        '<p><strong>PREFERRED SKILLS AND EXPERIENCE:</strong></p><ul><li>GPA of 3.5 or above</li></ul>'}
    profile = {'citizenship':'United States','education':{'gpa':gpa}}
    result = qualification_decision(posting,profile)
    assert result['status'] == 'qualified'
    assert result['checks'] == [{'constraint':'citizenship','verified':True},
        {'constraint':'gpa','verified':verified,'requirement':'preferred'}]
    assert result['posting_sha256'] == content_hash(posting)
    assert result['profile_sha256'] == content_hash(profile)


def test_unsupported_required_clause_after_preference_parks_backend_before_worker(tmp_path):
    from test_autonomous_backend import backend_with_candidate, FakeWorker
    from test_posting_qualifications import change_body
    from autonomous_controller import CandidateParked
    client = FakeWorker()
    backend,job = backend_with_candidate(tmp_path,client=client)
    change_body(backend,job,'Minimum GPA of 3.0\nPreferred Qualifications:\nGPA of 3.5 or above\nActive security clearance required')
    with pytest.raises(CandidateParked) as error:
        backend.prepare(job, lambda **_:None)
    assert error.value.state == 'blocked_fact'
    assert client.requests == []
    assert not list(backend.root.glob('attempts/*/manifest.json'))


def test_immediately_following_preferred_gpa_is_not_a_required_minimum():
    result = qualification_decision({'content':
        'Requirements:\nMinimum GPA of 3.0\nPREFERRED SKILLS AND EXPERIENCE:\nGPA of 3.5 or above'},
        {'education':{'gpa':3.2}})
    assert result['status'] == 'qualified'
    assert result['checks'] == [
        {'constraint':'gpa','verified':True},
        {'constraint':'gpa','verified':False,'requirement':'preferred'},
    ]


def test_preferred_heading_does_not_waive_explicit_minimum_wording():
    result = qualification_decision({'content':'Requirements:\nMinimum GPA of 3.0\nPreferred Qualifications:\nMinimum GPA of 3.5'},
        {'education':{'gpa':3.2}})
    assert result['status'] == 'blocked_fact'
    assert result['checks'][-1] == {'constraint':'gpa','verified':False}


def test_out_of_scale_preferred_threshold_remains_unverified_required_clause():
    result = qualification_decision({'content':
        'Minimum GPA of 3.0\nPreferred Qualifications:\nGPA of 4.5 or above'},
        {'education':{'gpa':3.2}})
    assert result['status'] == 'blocked_fact'
    assert result['checks'][-1] == {'constraint':'gpa','verified':False}
