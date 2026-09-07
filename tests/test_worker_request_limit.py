"""Whole-protocol byte cap, including commands not using WorkerConnection."""
import json
import pytest
from worker_operator import WorkerClient
from test_worker_operator import local_worker


def sized_payload(size):
    payload={'action':'ping','value':''}
    payload['value']='x'*(size-len(json.dumps(payload).encode())-1)
    assert len(json.dumps(payload).encode())+1==size
    return payload


def test_generic_worker_request_rejected_before_socket_or_path_access(tmp_path):
    with pytest.raises(ValueError,match='64-KiB'):
        WorkerClient(str(tmp_path/'never-opened.sock')).request(sized_payload(65536))


def test_generic_worker_request_under_limit_preserves_original_encoding():
    payload=sized_payload(65535)
    with local_worker([{'ok':True,'data':{'status':'fixture'}}]) as (path,requests):
        assert WorkerClient(path).request(payload)=={'status':'fixture'}
    assert requests==[payload]
