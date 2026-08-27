from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


PAGE_URL = "https://job-boards.greenhouse.io/fixture/REQ-123"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_live_inputs(tmp_path: Path) -> tuple[Path, Path, dict]:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    resume = runtime / "Resume.pdf"
    resume.write_bytes(b"%PDF-1.7\nsanitized live CLI resume")
    profile = runtime / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "personal": {"first_name": "Fixture"},
                "resume": {
                    "primary": str(resume),
                    "required_application_filename": "Resume.pdf",
                    "do_not_use_for_applications": [],
                },
            }
        )
    )
    answers = runtime / "approved-answers.json"
    answers.write_text(
        json.dumps(
            {
                "first_name": "Fixture",
                "last_name": "Person",
                "email": "fixture@example.test",
                "phone": "+1-555-0100",
                "resume": str(resume),
                "work_authorization": "Yes",
                "sponsorship": "No",
            }
        )
    )
    manifest = {
        "schema_version": 1,
        "mode": "sanitized_local",
        "job_id": 41,
        "queue_id": "queue-41",
        "target": {"id": "target-abc", "url": PAGE_URL},
        "identity": {
            "company": "Sanitized Example",
            "role": "Software Engineer Intern",
            "requisition": "REQ-123",
            "platform": "greenhouse",
            "tenant": "fixture",
        },
        "profile": {"path": str(profile), "sha256": _sha256(profile), "verified": True},
        "resume": {
            "path": str(resume),
            "basename": "Resume.pdf",
            "content_type": "application/pdf",
            "sha256": _sha256(resume),
            "verified": True,
        },
        "manual_gate": {
            "gates": [],
            "maango": False,
            "maango_approved": False,
            "verified": True,
        },
        "runtime_paths": {
            "preparation": str(runtime / "preparation.json"),
            "review": str(runtime / "review.json"),
            "authorization_db": str(runtime / "authorization.sqlite3"),
            "authorization_handoff": str(runtime / "authorization.handoff"),
            "submit_journal": str(runtime / "submit.jsonl"),
            "transaction_db": str(runtime / "transactions.sqlite3"),
            "status": str(runtime / "status.json"),
        },
    }
    manifest_path = runtime / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path, answers, manifest


def test_live_prepare_cli_exact_binds_runs_gates_uploads_profile_resume_and_persists_sanitized_evidence(
    tmp_path, capsys
):
    import production_operator

    manifest_path, answers_path, manifest = _write_live_inputs(tmp_path)
    fixture_html = (ROOT / "fixtures" / "local_operator_e2e.html").read_text()

    class Page:
        target_id = "target-abc"

        def __init__(self):
            self.values: dict[str, object] = {}
            self.uploaded_path = ""
            self.closed = False
            self.canary_selectors: list[str] = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.closed = True

        def read_only_snapshot(self):
            return {
                "target_id": self.target_id,
                "url": PAGE_URL,
                "html": fixture_html,
                "read_only": True,
            }

        def inspect_safety_surface(self, selectors):
            self.canary_selectors = list(selectors)
            return {
                "retina_scale": 2.0,
                "control_visible": True,
                "overlay_present": False,
                "native_window_detected": False,
            }

        def replace_text(self, selector, value):
            self.values[selector] = value

        def read_value(self, selector):
            return self.values[selector]

        def select_option(self, selector, value):
            self.values[selector] = value

        def read_selected_option(self, selector):
            return self.values[selector]

        def cdp_upload(self, selector, path):
            self.uploaded_path = path
            self.values[selector] = Path(path).name

        def read_uploaded_filename(self, selector):
            return self.values[selector]

    page = Page()
    bound_targets: list[tuple[str, str]] = []

    class Transport:
        def __init__(self, base_url):
            self.base_url = base_url

        def bind_mutable_page_target(self, target_id):
            bound_targets.append((self.base_url, target_id))
            return page

    result = production_operator.main(
        [
            "live",
            "prepare",
            "--manifest",
            str(manifest_path),
            "--approved-answers",
            str(answers_path),
            "--step",
            "application",
            "--cdp-base-url",
            "http://127.0.0.1:9222",
        ],
        live_transport_factory=Transport,
        live_health_probe=lambda base_url: {
            "status": "ready",
            "base_url": base_url,
            "recoverable": False,
        },
        live_coverage=lambda **kwargs: {
            "known": [{"question_key": "first_name", "source": "profile"}],
            "company_specific": [],
            "optional_skip": [],
            "human_required": [],
        },
    )

    assert result == 0
    assert bound_targets == [("http://127.0.0.1:9222", "target-abc")]
    assert page.closed is True
    assert set(page.canary_selectors) == {
        "#first_name",
        "#last_name",
        "#email",
        "#phone",
        "#resume",
        "#authorization",
        "#sponsorship",
    }
    assert page.uploaded_path == manifest["resume"]["path"]

    persisted_path = Path(manifest["runtime_paths"]["preparation"])
    persisted_text = persisted_path.read_text()
    persisted = json.loads(persisted_text)
    assert json.loads(capsys.readouterr().out) == persisted
    assert persisted["status"] == "prepared"
    assert persisted["submission_enabled"] is False
    assert persisted["review_ready"] is True
    assert persisted["manifest_binding"] == {
        "schema_version": 1,
        "mode": "sanitized_local",
        "job_id": 41,
        "queue_id": "queue-41",
        "tenant": "fixture",
    }
    assert persisted["health"] == {
        "browser_ready": True,
        "canary_passed": True,
        "exact_target_bound": True,
    }
    assert persisted["resume"] == {"basename": "Resume.pdf", "verified": True}
    assert len(persisted["applied_answers"]["field_evidence"]) == 7
    for sensitive in (
        "Fixture Person",
        "fixture@example.test",
        "+1-555-0100",
        str(tmp_path),
    ):
        assert sensitive not in persisted_text
