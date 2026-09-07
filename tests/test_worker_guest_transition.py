import pytest
from test_worker_operator import module, local_worker, URL


def test_after_submit_reader_follows_only_same_target_learned_route():
    bridge = module()
    assert hasattr(bridge.WorkerPage, 'read_after_submit_snapshot'), 'same-tab after-submit observation missing'
    after_url = URL + '/thank_you'
    replies=[{'ok':True,'data':[{'targetId':'target-1','url':after_url,'type':'page'}]}]
    replies += [{'ok':True,'data':{'binding':{'targetId':'target-1','url':after_url},'result':{'result':{'value':v}}}} for v in [after_url,'Thanks','Thank you for applying.','<html><body>Thank you for applying.</body></html>']]
    with local_worker(replies) as (path, requests):
        page=bridge.WorkerPage(target_id='target-1', target_url=URL, connection=bridge.WorkerConnection(bridge.WorkerClient(path),{'id':'target-1','url':URL}))
        with pytest.raises(ValueError, match='attempt'):
            page.read_after_submit_snapshot()
        page._submit_attempted=True  # synthetic already-journaled caller fixture
        after=page.read_after_submit_snapshot()
    assert after['url'] == after_url
    assert after['target_id'] == 'target-1'
    assert after['read_only'] is True


def test_confirmation_transport_requires_journal_and_same_target_receipt(tmp_path):
    from test_greenhouse_guest_confirmation import guest_context, TARGET, THANKYOU
    bridge=module(); context=guest_context(tmp_path)
    calls=[]
    class Client:
        def request(self, payload):
            calls.append(payload)
            return [{'targetId':TARGET,'url':THANKYOU,'type':'page'}]
    try:
        transport=bridge.WorkerTransport(Client(),target={'id':TARGET,'url':URL},confirmation_context=context)
    except TypeError:
        pytest.fail('receipt-bound confirmation transport missing')
    page=transport.bind_mutable_page_target(TARGET)
    assert page.target_url == THANKYOU
    with pytest.raises(ValueError, match='observation.only'):
        page._connection.call('Runtime.evaluate', {'expression':'document.body.click()', 'returnByValue':True})
    context['journal_path'].unlink()
    with pytest.raises(ValueError, match='journal'):
        bridge.WorkerTransport(Client(),target={'id':TARGET,'url':URL},confirmation_context=context)
    assert len(calls) == 1


def test_worker_refuses_oversized_json_before_touching_socket():
    bridge=module()
    with pytest.raises(ValueError,match='64.KiB'):
        bridge.WorkerClient('/not-opened').request({'expression':'x'*65536})


