"""Synthetic reduced explicit-preference clauses, not employer/candidate data."""
from posting_qualifications import qualification_decision, content_hash
import pytest

PREFERENCE = 'Minimum GPA of 3.5 or higher is preferred, but not required'


@pytest.mark.parametrize('value,verified', [(3.5,True),(4.0,True),(3.2,False),('3.5',False),(True,False),(None,False)])
@pytest.mark.parametrize('prefix', ['', '* '])
def test_explicit_preference_keeps_exact_fact_result_and_full_commitments(value, verified, prefix):
    posting = {'content':'U.S. citizenship required\n' + prefix + PREFERENCE}
    profile = {'citizenship':'United States','education':{'gpa':value}}
    result = qualification_decision(posting, profile)
    assert result['checks'][-1] == {'constraint':'gpa','verified':verified,'requirement':'preferred'}
    assert result['status'] == 'qualified'
    assert result['posting_sha256'] == content_hash(posting)
    assert result['profile_sha256'] == content_hash(profile)


@pytest.mark.parametrize('clause', [
    PREFERENCE + ' and active clearance',
    PREFERENCE + ' on a 5-point scale',
    PREFERENCE.replace('3.5', '4.1'),
    PREFERENCE.replace('3.5', '5.0'),
    PREFERENCE.replace('GPA', 'major GPA'),
    PREFERENCE.replace('not required', 'required'),
    PREFERENCE.replace('not required', 'not required for some applicants'),
    '&lt;p&gt;' + PREFERENCE + '&lt;/p&gt;',
    '** ' + PREFERENCE,
    'Minimum GPA of 3.5 or higher',
])
def test_nearby_or_compound_wording_never_receives_preference_waiver(clause):
    result = qualification_decision({'content':'U.S. citizenship required\n' + clause},
                                    {'citizenship':'United States','education':{'gpa':3.2}})
    assert result['status'] == 'blocked_fact'
    assert 'requirement' not in result['checks'][-1]


@pytest.mark.parametrize('body', [
    PREFERENCE,
    PREFERENCE + '\nMinimum GPA of 3.8',
    'Minimum GPA of 3.8\n' + PREFERENCE,
    'U.S. citizenship required\n' + PREFERENCE + ';Active clearance required',
    'Desired:\n' + PREFERENCE,
])
def test_preference_does_not_erase_other_clauses_or_establish_eligibility_alone(body):
    result = qualification_decision({'content':body}, {'citizenship':'United States','education':{'gpa':3.2}})
    assert result['status'] == 'blocked_fact'
    assert any(c.get('requirement') == 'preferred' for c in result['checks'])


def test_unverified_required_body_still_parks_before_worker_or_attempt(tmp_path):
    from test_autonomous_backend import backend_with_candidate, FakeWorker
    from test_posting_qualifications import change_body
    from autonomous_controller import CandidateParked
    client = FakeWorker()
    backend, job = backend_with_candidate(tmp_path, client=client)
    change_body(backend, job, 'Minimum GPA of 3.0\n* ' + PREFERENCE + '\nPre-employment drug screening required')
    with pytest.raises(CandidateParked) as error:
        backend.prepare(job, lambda **_:None)
    assert error.value.state == 'blocked_fact'
    assert client.requests == []
    assert not list(backend.root.glob('attempts/*/manifest.json'))


def test_explicit_not_required_gpa_is_not_a_mandatory_minimum():
    posting = {'content': '<p>U.S. citizenship required</p>'
               '<p>* Minimum GPA of 3.5 or higher is preferred, but not required</p>'}
    profile = {'citizenship':'United States', 'education':{'gpa':3.2}}
    result = qualification_decision(posting, profile)
    assert result['checks'] == [
        {'constraint':'citizenship','verified':True},
        {'constraint':'gpa','verified':False,'requirement':'preferred'},
    ]
    assert result['status'] == 'qualified'
