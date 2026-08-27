from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_real_local_chrome_exact_cdp_operator_flow_and_safety_recovery(tmp_path):
    import browser_integration_canary
    import confirmation_reconciliation
    import local_cdp_operator
    import mutable_cdp_page_adapter
    import one_shot_submit
    import page_recovery
    import post_submit_transaction
    import prepare_live_job
    import review_reconciler
    import submission_authorization
    import tenant_field_maps
    import visual_escalation

    fixture = ROOT / "fixtures" / "local_operator_e2e.html"
    resume = tmp_path / "Resume.pdf"
    resume.write_bytes(b"%PDF-1.7\nsanitized local fixture resume")
    resume_sha256 = hashlib.sha256(resume.read_bytes()).hexdigest()
    expected_identity = {
        "company": "Sanitized Example",
        "role": "Software Engineer Intern",
        "requisition": "REQ-123",
    }

    with local_cdp_operator.LocalChromeFixtureSession(
        fixture_path=fixture,
        chrome_path=local_cdp_operator.find_local_chrome_for_testing(),
        runtime_dir=tmp_path / "chrome-runtime",
    ) as session:
        target_id = session.target_id
        with session.bind_exact_page(target_id) as page:
            page.set_retina_scale_for_test(2.0)
            snapshot = page.read_only_snapshot()
            assert snapshot["device_scale_factor"] == 2
            assert browser_integration_canary.run_canary(
                "greenhouse",
                {
                    "retina_scale": snapshot["device_scale_factor"],
                    "target_current": True,
                    "control_visible": True,
                    "overlay_present": False,
                    "native_window_detected": False,
                    "submission_enabled": False,
                },
            )["status"] == "passed"

            page.toggle_overlay_for_test(True)
            assert browser_integration_canary.run_canary(
                "greenhouse",
                {
                    "retina_scale": 2,
                    "target_current": True,
                    "control_visible": True,
                    "overlay_present": True,
                    "native_window_detected": False,
                    "submission_enabled": False,
                },
            )["reason"] == "overlay_present"
            with pytest.raises(mutable_cdp_page_adapter.PageControlError, match="visible, enabled, and unobscured"):
                page.replace_text("#first_name", "must not be written through overlay")
            page.toggle_overlay_for_test(False)

            ocr_result = visual_escalation.execute_with_scoped_ocr_escalation(
                lambda: {"verified": False, "reason": "sanitized fixture needs visual observation"},
                lambda reason: {
                    "scope": f"exact-target:{target_id}",
                    "text": "Review application" if page.capture_scoped_screenshot().startswith(b"\x89PNG") else "",
                    "observation_only": True,
                },
                lambda evidence: {
                    "verified": evidence.get("text") == "Review application",
                    "evidence": "exact-page observation only",
                },
            )
            assert ocr_result["status"] == "completed"
            assert ocr_result["scoped_screenshot_ocr_attempts"] == 1

            actions = [
                {"field": "first_name", "operation": "replace_text", "selector": "#first_name", "value": "Fixture Person"},
                {"field": "resume", "operation": "cdp_upload", "selector": "#resume", "value": str(resume)},
                {"field": "work_authorization", "operation": "native_select", "selector": "#authorization", "value": "Yes"},
            ]
            prepared = prepare_live_job.prepare_live_job(
                page=page,
                target_id=target_id,
                expected_url=session.page_url,
                expected_identity=expected_identity,
                profile={},
                prepare=lambda **kwargs: {
                    "platform": "greenhouse",
                    **expected_identity,
                    "questions": [],
                    "submission_enabled": False,
                },
                coverage=lambda **kwargs: {
                    "known": [],
                    "company_specific": [],
                    "optional_skip": [],
                    "human_required": [],
                },
                approved_answers={item["field"]: item["value"] for item in actions},
                apply_known=lambda answers: tenant_field_maps.execute_step_actions(
                    page=page,
                    target_id=target_id,
                    expected_url=session.page_url,
                    actions=actions,
                ),
            )
            prepared = prepare_live_job._sanitize_review_evidence(prepared)
            assert prepared["review_ready"] is True
            page.wait_for_resume_sha256(resume_sha256)
            page.activate_review("#review")

            authoritative = review_reconciler.reconcile_review(
                preparation_evidence=prepared,
                server_review=page.read_server_review(),
                expected_target={
                    "target_id": target_id,
                    "page_url": session.page_url,
                    **expected_identity,
                },
                profile_fields={"#first_name": "Fixture Person", "#authorization": "Yes"},
                resume_preflight={
                    "basename": "Resume.pdf",
                    "content_type": "application/pdf",
                    "sha256": resume_sha256,
                    "verified": True,
                },
                required_parser_repairs=[],
                required_question_ids=["work_authorization"],
            )
            assert authoritative["review_authoritative"] is True

            authorization_db = tmp_path / "authorization.db"
            store = submission_authorization.SubmissionAuthorizationStore(authorization_db)
            issued = store.issue(
                job_id=17,
                review_evidence=authoritative,
                actor="fixture-operator",
                issued_at="2026-08-27T08:00:00+00:00",
                expires_at="2026-08-27T08:05:00+00:00",
            )

            class InterruptAfterExactClick:
                def __getattr__(self, name):
                    return getattr(page, name)

                def click_submit_once(self, selector):
                    page.click_submit_once(selector)
                    raise one_shot_submit.SubmitInterrupted("sanitized post-click interruption")

            journal_path = tmp_path / "page-actions.jsonl"
            submitted = one_shot_submit.execute_one_shot_submit(
                authorization_store=store,
                token=issued["token"],
                page=InterruptAfterExactClick(),
                journal_path=journal_path,
                job_id=17,
                target_id=target_id,
                expected_url=session.page_url,
                requisition="REQ-123",
                review_evidence_sha256=authoritative["review_evidence_sha256"],
                actor="fixture-operator",
                now="2026-08-27T08:01:00+00:00",
                submit_selector="#submit",
            )
            assert submitted["status"] == "confirmation_observed"
            assert submitted["recovered_by_inspection"] is True
            assert page.read_submit_count() == 1

        with session.bind_exact_page(target_id) as restarted_page:
            assert restarted_page.inspect_confirmation()["confirmed"] is True
            assert page_recovery.resume_from_verified_page_state(journal_path) == {
                "status": "resumable",
                "next_action": "inspect_page",
            }
            restarted_store = submission_authorization.SubmissionAuthorizationStore(authorization_db)
            with pytest.raises(PermissionError, match="replayed"):
                restarted_store.consume(
                    token=issued["token"],
                    current_binding={
                        "job_id": 17,
                        "target_id": target_id,
                        "page_url": session.page_url,
                        "requisition": "REQ-123",
                        "review_evidence_sha256": authoritative["review_evidence_sha256"],
                    },
                    actor="fixture-operator",
                    now="2026-08-27T08:02:00+00:00",
                )
            assert restarted_page.read_submit_count() == 1

            confirmation = confirmation_reconciliation.extract_confirmation(
                platform="greenhouse",
                html_text=restarted_page.read_only_snapshot()["html"],
                page_url=session.page_url,
            )
            portal = confirmation_reconciliation.reconcile_candidate_portal(
                confirmation=confirmation,
                expected_identity=expected_identity,
                candidate_applications=restarted_page.read_candidate_applications(),
            )
            assert portal["portal_confirmed"] is True

            events = []

            class LocalTracker:
                record = None

                def append(self, **kwargs):
                    events.append("tracker.append")
                    self.record = kwargs

                def read_back(self, *, transaction_id):
                    events.append("tracker.read_back")
                    if not self.record:
                        return None
                    return {"verified": True, "transaction_id": transaction_id, "payload_sha256": self.record["payload_sha256"], "receipt_id": "local-row"}

            class LocalDiscord:
                record = None

                def send(self, **kwargs):
                    events.append("discord.send")
                    self.record = kwargs

                def read_back(self, *, transaction_id):
                    events.append("discord.read_back")
                    if not self.record:
                        return None
                    return {"verified": True, "transaction_id": transaction_id, "message_sha256": self.record["message_sha256"], "receipt_id": "local-message"}

            final = post_submit_transaction.PostSubmitTransactionCoordinator(
                state_path=tmp_path / "post-submit.db",
                tracker=LocalTracker(),
                discord=LocalDiscord(),
            ).run(
                job_id=17,
                portal_evidence=portal,
                tracker_payload={"status": "Submitted - Pending Response"},
                discord_message="Sanitized fixture submitted",
            )
            assert final["status"] == "complete"
            assert events == ["tracker.read_back", "tracker.append", "tracker.read_back", "discord.read_back", "discord.send", "discord.read_back"]

            restarted_page.drift_url_for_test()
            with pytest.raises(mutable_cdp_page_adapter.StaleTargetError, match="target URL changed"):
                restarted_page.replace_text("#first_name", "must not replay")
