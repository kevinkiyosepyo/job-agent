from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import kevin_bible_sync


def test_sync_caches_source_timestamp_and_reports_profile_precedence_without_pii_in_logs(tmp_path):
    cache_path = tmp_path / "runtime" / "kevin-bible-cache.json"
    logs: list[str] = []
    document = {
        "revisionId": "revision-42",
        "modifiedTime": "2026-08-25T09:00:00Z",
        "answers": [
            {
                "question_key": "graduation_season",
                "answer": "Winter 2027",
                "contact": "kevinkpyo@gmail.com",
            }
        ],
    }
    profile = {"education": {"graduation_season": "Spring 2028"}}

    result = kevin_bible_sync.sync(
        doc_id="doc-123",
        profile=profile,
        cache_path=cache_path,
        fetch_document=lambda _: document,
        log=logs.append,
        now="2026-08-25T10:00:00Z",
    )

    cached = json.loads(cache_path.read_text())
    assert cached["source"] == {
        "doc_id": "doc-123",
        "revision_id": "revision-42",
        "modified_at": "2026-08-25T09:00:00Z",
        "fetched_at": "2026-08-25T10:00:00Z",
    }
    assert cached["answers"] == document["answers"]
    assert result["conflicts"] == [
        {
            "question_key": "graduation_season",
            "winner": "profile",
            "discarded_source": "kevin_bible",
        }
    ]
    assert all("kevinkpyo@gmail.com" not in entry for entry in logs)
