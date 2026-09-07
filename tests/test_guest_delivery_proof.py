"""SYNTHETIC guest evidence and in-process notification adapter, no network."""
import copy
import pytest
from test_greenhouse_guest_confirmation import guest_context, reconcile
from post_submit_transaction import PostSubmitTransactionCoordinator, _validate_portal
from production_operator import _TimedLocalDiscord


def test_guest_outbox_can_resume_without_losing_provenance(tmp_path):
    portal=reconcile(guest_context(tmp_path))
    discord=_TimedLocalDiscord()
    coordinator=PostSubmitTransactionCoordinator(state_path=tmp_path/'outbox.sqlite3',discord=discord)
    result=coordinator.run(job_id=8171772,portal_evidence=portal,discord_message='SYNTHETIC offline guest result',deliver=False)
    assert result['notification_state']=='pending'
    restarted=PostSubmitTransactionCoordinator(state_path=tmp_path/'outbox.sqlite3',discord=discord)
    assert restarted.resume_notification(job_id=8171772)['notification_state']=='delivered'


@pytest.mark.parametrize('damage',['missing_proof','body_hash','requisition','replay','applicable','unchanged_html'])
def test_guest_delivery_rejects_damaged_confirmation_proof(tmp_path,damage):
    portal=reconcile(guest_context(tmp_path))
    _validate_portal(portal)
    if damage=='missing_proof':portal['evidence'].pop('provenance')
    elif damage=='body_hash':portal['evidence']['provenance']['after_body_text_sha256']='0'*64
    elif damage=='requisition':portal['evidence']['provenance']['binding']['requisition']='OTHER'
    elif damage=='replay':portal['replay_allowed']=True
    elif damage=='applicable':portal['portal_readback']['applicable']=True
    elif damage=='unchanged_html':portal['evidence']['provenance']['after_html_sha256']=portal['evidence']['provenance']['before_html_sha256']
    with pytest.raises(ValueError,match='verified portal confirmation'):
        _validate_portal(portal)
