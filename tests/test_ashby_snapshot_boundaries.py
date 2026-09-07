"""Synthetic boundary regressions; no employer data or network access."""
import pytest
import sources
from test_sources import FakeResponse


def test_explicit_empty_snapshot_path_never_falls_back_to_network(tmp_path, monkeypatch):
    requests = []
    def fake_open(url, timeout):
        requests.append(url)
        return FakeResponse({"jobs": []})
    monkeypatch.setattr(sources, "urlopen", fake_open)
    output = tmp_path / "output.json"
    with pytest.raises(SystemExit) as error:
        sources.main(["--ashby", "example", "--ashby-snapshot", "", "--output", str(output)])
    assert error.value.code == 2
    assert requests == []
    assert not output.exists()


@pytest.mark.parametrize("posting_id", ["../other/1", "extra/path", "..", ".",
    "%2e%2e", "%2Fother", r"..\other\1", "%252e%252e"])
def test_posting_identity_rejects_nonsegment_ids_before_url_matching(posting_id):
    raw = {"jobs": [{"id": posting_id, "title": "Synthetic Software Intern", "isListed": True,
        "jobUrl": f"https://jobs.ashbyhq.com/example/{posting_id}"}]}
    result = sources.discover_jobs(ashby=["example"], opener=lambda *args: FakeResponse(raw))
    assert result["exit_code"] == 1
    assert result["jobs"] == []
    assert "single path segment" in result["report"]["failures"][0]["error"]
