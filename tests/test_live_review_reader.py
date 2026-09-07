from __future__ import annotations

import sys
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_mapped_review_reads_text_tel_react_checkbox_and_rendered_resume():
    import live_review_reader

    class Page:
        def read_only_snapshot(self):
            return {
                "read_only": True,
                "target_id": "page-42",
                "url": "https://job-boards.greenhouse.io/example/jobs/123",
            }

        def read_value(self, selector):
            return {"#name": "Kevin", "#phone": "(571) 435-5734"}[selector]

        def read_react_selected_option(self, selector):
            return "No"

        def read_checked(self, selector):
            return True

        def read_uploaded_filename(self, selector):
            return "Resume 2027 SWE.pdf"

        def read_uploaded_sha256(self, selector):
            return ""

    mapping = {
        "platform": "greenhouse",
        "steps": {
            "application": {
                "controls": {
                    "name": {"selector": "#name", "operation": "replace_text"},
                    "phone": {"selector": "#phone", "operation": "replace_tel_local_digits"},
                    "sponsorship": {"selector": "#sponsorship", "operation": "react_select_exact"},
                    "privacy": {"selector": "#privacy", "operation": "set_checked"},
                    "resume": {"selector": "#resume", "operation": "cdp_upload"},
                }
            }
        },
    }

    review = live_review_reader.read_server_review(
        page=Page(),
        platform="greenhouse",
        mapping=mapping,
        step="application",
        target_id="page-42",
        page_url="https://job-boards.greenhouse.io/example/jobs/123",
        identity={"company": "Example", "role": "Intern", "requisition": "123"},
        required_parser_repairs=[],
        required_question_ids=[],
    )

    assert review["fields"] == {
        "#name": "Kevin",
        "#phone": "5714355734",
        "#sponsorship": "No",
        "#privacy": True,
    }
    assert review["resume"] == {
        "basename": "Resume 2027 SWE.pdf",
        "sha256": "",
        "verified": False,
    }
    assert review["source"] == "unverified_mapped_form"
    assert review["server_saved"] is False


@pytest.mark.parametrize("metadata", [{}, {"source": "server_saved_review", "server_saved": False}])
def test_learned_reader_does_not_invent_missing_or_contradictory_provenance(metadata):
    import live_review_reader
    class Page:
        def read_only_snapshot(self):
            return {"read_only": True, "target_id": "p", "url": "https://example.test/review"}
        def read_server_review(self):
            return dict(metadata)
    with pytest.raises(live_review_reader.LiveReviewReadError, match="provenance"):
        live_review_reader.read_server_review(page=Page(), platform="workday", mapping={"platform": "workday"},
            step="review", target_id="p", page_url="https://example.test/review", identity={},
            required_parser_repairs=[], required_question_ids=[])
