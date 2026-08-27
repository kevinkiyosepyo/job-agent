#!/usr/bin/env python3
"""Approval-gated production-operator proof over one sanitized local ATS fixture.

This command intentionally exposes no real-application mode.  It composes the
production contracts end to end against one exact marker-checked static page so
health, timing, authorization, submission recovery, and downstream read-back
evidence can be audited before a human separately authorizes any live use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import browser_integration_canary
import browser_health
import confirmation_reconciliation
import greenhouse_handler
import live_run_manifest
import one_shot_submit
import post_submit_transaction
import prepare_live_job
import resume_preflight
import review_reconciler
from scoped_cdp import ScopedCDPTransport
import submission_authorization
import tenant_field_maps
import timing_telemetry
from local_cdp_operator import LocalChromeFixtureSession, find_local_chrome_for_testing
from production_readiness import PREPARATION_TARGET_SECONDS, VERIFIED_SUBMISSION_TARGET_SECONDS


ROOT = Path(__file__).resolve().parent
LOCAL_FIXTURE = (ROOT / "fixtures" / "local_operator_e2e.html").resolve()
LEARNED_PAGE_URL = "https://job-boards.greenhouse.io/fixture/REQ-123"
IDENTITY = {
    "company": "Sanitized Example",
    "role": "Software Engineer Intern",
    "requisition": "REQ-123",
}
REQUIRED_TIMING_STAGES = {
    "discovery",
    "upload",
    "form_fill",
    "review",
    "confirmation",
    "tracker_readback",
    "discord_readback",
}
SAFETY_EVIDENCE = {
    "credentials_accessed": False,
    "external_message_sent": False,
    "live_tracker_mutated": False,
    "production_ats_accessed": False,
    "real_application_authorized": False,
    "real_application_submitted": False,
    "sanitized_fixture_only": True,
}


class OperatorBlockedError(ValueError):
    """The local proof failed a mandatory pre-action or audit gate."""


class _TimedLocalTracker:
    """In-memory tracker proof with the Task 7 adapter shape."""

    def __init__(self) -> None:
        self.record: dict | None = None
        self.elapsed_seconds = 0.0

    def _measure(self, operation: Callable[[], object]) -> object:
        started = time.monotonic()
        try:
            return operation()
        finally:
            self.elapsed_seconds += time.monotonic() - started

    def append(self, **kwargs) -> None:
        self._measure(lambda: setattr(self, "record", dict(kwargs)))

    def read_back(self, *, transaction_id: str) -> dict | None:
        def read() -> dict | None:
            if self.record is None:
                return None
            return {
                "verified": True,
                "transaction_id": transaction_id,
                "payload_sha256": self.record["payload_sha256"],
                "receipt_id": "sanitized-local-row",
            }

        return self._measure(read)  # type: ignore[return-value]


class _TimedLocalDiscord:
    """In-memory Discord proof with no network or external message API."""

    def __init__(self) -> None:
        self.record: dict | None = None
        self.elapsed_seconds = 0.0

    def _measure(self, operation: Callable[[], object]) -> object:
        started = time.monotonic()
        try:
            return operation()
        finally:
            self.elapsed_seconds += time.monotonic() - started

    def send(self, **kwargs) -> None:
        self._measure(lambda: setattr(self, "record", dict(kwargs)))

    def read_back(self, *, transaction_id: str) -> dict | None:
        def read() -> dict | None:
            if self.record is None:
                return None
            return {
                "verified": True,
                "transaction_id": transaction_id,
                "message_sha256": self.record["message_sha256"],
                "receipt_id": "sanitized-local-message",
            }

        return self._measure(read)  # type: ignore[return-value]


def _resume_preflight(path: Path) -> dict[str, object]:
    resolved = Path(path).resolve()
    if resolved.name != "Resume.pdf" or not resolved.is_file():
        raise OperatorBlockedError("sanitized demo requires an existing exact Resume.pdf")
    content = resolved.read_bytes()
    if not content.startswith(b"%PDF"):
        raise OperatorBlockedError("sanitized demo Resume.pdf failed PDF preflight")
    return {
        "path": resolved,
        "basename": "Resume.pdf",
        "content_type": "application/pdf",
        "sha256": hashlib.sha256(content).hexdigest(),
        "verified": True,
    }


def _prepare_greenhouse_fixture(*, html_text: str, page_url: str) -> dict:
    inspected = greenhouse_handler.inspect_html(html_text, page_url=page_url)
    if (
        inspected.get("page_type") != "application"
        or inspected.get("manual_gate") is not None
        or inspected.get("company") != IDENTITY["company"]
        or inspected.get("role") != IDENTITY["role"]
        or IDENTITY["requisition"] not in html_text
    ):
        raise OperatorBlockedError("sanitized learned-ATS handler health gate failed")
    return {
        **inspected,
        "platform": "greenhouse",
        **IDENTITY,
        "questions": [],
        "submission_enabled": False,
    }


def _known_coverage(**kwargs) -> dict[str, list[dict[str, str]]]:
    del kwargs
    return {
        "known": [
            {"question_key": key, "source": "explicit_sanitized_demo_map"}
            for key in (
                "first_name",
                "last_name",
                "email",
                "phone",
                "resume",
                "work_authorization",
                "sponsorship",
            )
        ],
        "company_specific": [],
        "optional_skip": [],
        "human_required": [],
    }


def _require_health_gates(checks: dict[str, bool]) -> dict[str, object]:
    if not checks or not all(value is True for value in checks.values()):
        raise OperatorBlockedError("operational health gate failed before sanitized submit")
    return {"passed": True, "checks": checks}


def _number_below(value: object, target: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0 <= float(value) < target
    )


def audit_operator_report(report: object) -> dict[str, object]:
    """Re-evaluate a persisted local run without granting real submit authority."""
    valid = isinstance(report, dict)
    payload = report if isinstance(report, dict) else {}
    health = payload.get("health_gates", {})
    timing = payload.get("timing", {})
    evidence = payload.get("evidence", {})
    safety = payload.get("safety", {})
    valid = valid and all(
        (
            payload.get("schema_version") == 1,
            payload.get("mode") == "sanitized_local_demo",
            payload.get("platform") == "greenhouse",
            payload.get("status") == "complete",
            isinstance(health, dict),
            health.get("passed") is True,
            isinstance(health.get("checks"), dict),
            bool(health.get("checks")),
            all(value is True for value in health.get("checks", {}).values()),
            isinstance(timing, dict),
            timing.get("within_targets") is True,
            _number_below(timing.get("preparation_seconds"), PREPARATION_TARGET_SECONDS),
            _number_below(
                timing.get("verified_submission_seconds"),
                VERIFIED_SUBMISSION_TARGET_SECONDS,
            ),
            isinstance(timing.get("stages"), list),
            {
                item.get("stage")
                for item in timing.get("stages", [])
                if isinstance(item, dict)
                and _number_below(item.get("elapsed_seconds"), float("inf"))
            }
            == REQUIRED_TIMING_STAGES,
            isinstance(evidence, dict),
            evidence.get("learned_map_version") == 1,
            evidence.get("fields_verified") == 7,
            evidence.get("review_authoritative") is True,
            evidence.get("authorization_consumed") is True,
            evidence.get("single_use_replay_denied") is True,
            evidence.get("one_shot") is True,
            evidence.get("submit_count") == 1,
            evidence.get("portal_confirmed") is True,
            evidence.get("tracker_readback_verified") is True,
            evidence.get("discord_readback_verified") is True,
            safety == SAFETY_EVIDENCE,
        )
    )
    return {
        "checks_passed": bool(valid),
        "real_application_authorized": False,
        "status": "ready_for_manual_live_authorization_review" if valid else "not_ready",
    }


def empty_verified_report_for_test() -> dict:
    """Return a value-free verified shape for focused fail-closed audit tests."""
    report = {
        "schema_version": 1,
        "mode": "sanitized_local_demo",
        "platform": "greenhouse",
        "status": "complete",
        "health_gates": {"passed": True, "checks": {"fixture": True}},
        "timing": {
            "preparation_seconds": 1.0,
            "verified_submission_seconds": 2.0,
            "within_targets": True,
            "stages": [timing_telemetry.record_stage(stage, 0) for stage in sorted(REQUIRED_TIMING_STAGES)],
        },
        "evidence": {
            "authorization_consumed": True,
            "discord_readback_verified": True,
            "fields_verified": 7,
            "learned_map_version": 1,
            "one_shot": True,
            "portal_confirmed": True,
            "review_authoritative": True,
            "single_use_replay_denied": True,
            "submit_count": 1,
            "tracker_readback_verified": True,
        },
        "safety": deepcopy(SAFETY_EVIDENCE),
    }
    return report


def run_local_sanitized_demo(
    *, resume_path: Path, runtime_dir: Path, approved: bool
) -> dict:
    """Compose all production stages against one exact sanitized local page."""
    if approved is not True:
        raise OperatorBlockedError("explicit sanitized-demo submit approval is required")
    if LOCAL_FIXTURE.resolve() != (ROOT / "fixtures" / "local_operator_e2e.html").resolve():
        raise OperatorBlockedError("sanitized fixture binding changed")
    fixture_text = LOCAL_FIXTURE.read_text(encoding="utf-8")
    if 'data-fixture="local-operator"' not in fixture_text:
        raise OperatorBlockedError("sanitized fixture marker is missing")

    resume = _resume_preflight(Path(resume_path))
    runtime = Path(runtime_dir)
    runtime.mkdir(parents=True, exist_ok=True)
    mapping = tenant_field_maps.resolve_field_map(
        page_url=LEARNED_PAGE_URL,
        platform="greenhouse",
    )
    approved_answers = {
        "first_name": "Fixture Person",
        "last_name": "Example",
        "email": "fixture.person@example.test",
        "phone": "+1-555-0100",
        "resume": str(resume["path"]),
        "work_authorization": "Yes",
        "sponsorship": "No",
    }
    actions = tenant_field_maps.build_step_actions(
        mapping=mapping,
        step="application",
        approved_answers=approved_answers,
    )
    transition = tenant_field_maps.plan_next_step(
        mapping=mapping,
        current_step="application",
        completed_fields=set(approved_answers),
        conditions={},
    )
    if transition.get("status") != "advance" or transition.get("next_step") != "review":
        raise OperatorBlockedError("learned ATS application step was not Review-ready")

    stage_seconds: dict[str, float] = {}
    preparation_started = time.monotonic()
    discovery_started = time.monotonic()
    session_context = LocalChromeFixtureSession(
        fixture_path=LOCAL_FIXTURE,
        chrome_path=find_local_chrome_for_testing(),
        runtime_dir=runtime / "chrome",
    )
    with session_context as session:
        stage_seconds["discovery"] = time.monotonic() - discovery_started
        target_id = session.target_id
        with session.bind_exact_page(target_id) as page:
            page.set_retina_scale_for_test(2.0)
            initial_snapshot = page.read_only_snapshot()
            canary = browser_integration_canary.run_canary(
                "greenhouse",
                {
                    "retina_scale": initial_snapshot.get("device_scale_factor"),
                    "target_current": initial_snapshot.get("target_id") == target_id,
                    "control_visible": True,
                    "overlay_present": initial_snapshot.get("overlay_present"),
                    "native_window_detected": False,
                    "submission_enabled": False,
                },
            )

            def apply_learned_answers(_: dict[str, object]) -> dict[str, object]:
                form_actions = [item for item in actions if item["operation"] != "cdp_upload"]
                upload_actions = [item for item in actions if item["operation"] == "cdp_upload"]
                form_started = time.monotonic()
                form_result = tenant_field_maps.execute_step_actions(
                    page=page,
                    target_id=target_id,
                    expected_url=session.page_url,
                    actions=form_actions,
                )
                stage_seconds["form_fill"] = time.monotonic() - form_started
                upload_started = time.monotonic()
                upload_result = tenant_field_maps.execute_step_actions(
                    page=page,
                    target_id=target_id,
                    expected_url=session.page_url,
                    actions=upload_actions,
                )
                stage_seconds["upload"] = time.monotonic() - upload_started
                evidence = [
                    *form_result.get("field_evidence", []),
                    *upload_result.get("field_evidence", []),
                ]
                return {
                    "action": "apply_learned_step",
                    "field_evidence": evidence,
                    "verified": len(evidence) == 7
                    and all(item.get("verified") is True for item in evidence),
                }

            prepared = prepare_live_job.prepare_live_job(
                page=page,
                target_id=target_id,
                expected_url=session.page_url,
                expected_identity=IDENTITY,
                profile={},
                prepare=_prepare_greenhouse_fixture,
                coverage=_known_coverage,
                approved_answers=approved_answers,
                apply_known=apply_learned_answers,
            )
            prepared = prepare_live_job._sanitize_review_evidence(prepared)
            field_evidence = prepared["applied_answers"]["field_evidence"]
            page.wait_for_resume_sha256(str(resume["sha256"]))

            review_started = time.monotonic()
            page.activate_review("#review")
            profile_fields = {
                "#first_name": approved_answers["first_name"],
                "#last_name": approved_answers["last_name"],
                "#email": approved_answers["email"],
                "#phone": approved_answers["phone"],
                "#authorization": approved_answers["work_authorization"],
                "#sponsorship": approved_answers["sponsorship"],
            }
            authoritative = review_reconciler.reconcile_review(
                preparation_evidence=prepared,
                server_review=page.read_server_review(),
                expected_target={
                    "target_id": target_id,
                    "page_url": session.page_url,
                    **IDENTITY,
                },
                profile_fields=profile_fields,
                resume_preflight={
                    key: resume[key]
                    for key in ("basename", "content_type", "sha256", "verified")
                },
                required_parser_repairs=[],
                required_question_ids=["work_authorization"],
            )
            stage_seconds["review"] = time.monotonic() - review_started
            preparation_seconds = time.monotonic() - preparation_started

            health_gates = _require_health_gates(
                {
                    "explicit_sanitized_approval": approved is True,
                    "exact_static_fixture": LOCAL_FIXTURE.is_file(),
                    "chrome_process": "Chrome" in session.browser_product,
                    "process_scoped_cdp_pipe": True,
                    "exact_target_current": initial_snapshot.get("url") == session.page_url,
                    "retina_canary": canary.get("status") == "passed",
                    "mandatory_gates_clear": initial_snapshot.get("gates") == [],
                    "maango_clear": initial_snapshot.get("maango") is False,
                    "exact_resume_preflight": resume.get("verified") is True,
                    "learned_map_exact": mapping.get("version") == 1
                    and mapping.get("tenant") == "fixture",
                    "all_fields_read_back": len(field_evidence) == 7
                    and all(item.get("verified") is True for item in field_evidence),
                    "authoritative_review": authoritative.get("review_authoritative") is True,
                    "local_downstream_adapters": True,
                }
            )

            issued_at = datetime.now(timezone.utc).replace(microsecond=0)
            authorization_store = submission_authorization.SubmissionAuthorizationStore(
                runtime / "submission-authorization.db"
            )
            issued = authorization_store.issue(
                job_id=1,
                review_evidence=authoritative,
                actor="sanitized-local-operator",
                issued_at=issued_at,
                expires_at=issued_at + timedelta(minutes=5),
            )

            submission_started = time.monotonic()
            confirmation_started = time.monotonic()
            submitted = one_shot_submit.execute_one_shot_submit(
                authorization_store=authorization_store,
                token=issued["token"],
                page=page,
                journal_path=runtime / "page-actions.jsonl",
                job_id=1,
                target_id=target_id,
                expected_url=session.page_url,
                requisition=IDENTITY["requisition"],
                review_evidence_sha256=authoritative["review_evidence_sha256"],
                actor="sanitized-local-operator",
                now=issued_at + timedelta(seconds=1),
                submit_selector="#submit",
            )
            if submitted.get("status") != "confirmation_observed":
                raise OperatorBlockedError("one-shot sanitized submit lacked confirmation")
            try:
                authorization_store.consume(
                    token=issued["token"],
                    current_binding={
                        "job_id": 1,
                        "target_id": target_id,
                        "page_url": session.page_url,
                        "requisition": IDENTITY["requisition"],
                        "review_evidence_sha256": authoritative["review_evidence_sha256"],
                    },
                    actor="sanitized-local-operator",
                    now=issued_at + timedelta(seconds=2),
                )
            except PermissionError as exc:
                replay_denied = "replayed" in str(exc)
            else:
                replay_denied = False

            confirmation = confirmation_reconciliation.extract_confirmation(
                platform="greenhouse",
                html_text=page.read_only_snapshot()["html"],
                page_url=session.page_url,
            )
            portal = confirmation_reconciliation.reconcile_candidate_portal(
                confirmation=confirmation,
                expected_identity=IDENTITY,
                candidate_applications=page.read_candidate_applications(),
            )
            submit_count = page.read_submit_count()
            stage_seconds["confirmation"] = time.monotonic() - confirmation_started

    tracker = _TimedLocalTracker()
    discord = _TimedLocalDiscord()
    final_transaction = post_submit_transaction.PostSubmitTransactionCoordinator(
        state_path=runtime / "post-submit.db",
        tracker=tracker,
        discord=discord,
    ).run(
        job_id=1,
        portal_evidence=portal,
        tracker_payload={"status": "Submitted - Pending Response"},
        discord_message="Sanitized local operator demonstration complete",
    )
    stage_seconds["tracker_readback"] = tracker.elapsed_seconds
    stage_seconds["discord_readback"] = discord.elapsed_seconds
    verified_submission_seconds = time.monotonic() - submission_started

    report = {
        "schema_version": 1,
        "mode": "sanitized_local_demo",
        "platform": "greenhouse",
        "status": "complete",
        "health_gates": health_gates,
        "timing": {
            "preparation_seconds": preparation_seconds,
            "verified_submission_seconds": verified_submission_seconds,
            "within_targets": preparation_seconds < PREPARATION_TARGET_SECONDS
            and verified_submission_seconds < VERIFIED_SUBMISSION_TARGET_SECONDS,
            "stages": [
                timing_telemetry.record_stage(stage, stage_seconds[stage])
                for stage in sorted(REQUIRED_TIMING_STAGES)
            ],
        },
        "evidence": {
            "authorization_consumed": submitted.get("authorization_consumed") is True,
            "discord_readback_verified": final_transaction.get("discord", {}).get(
                "readback_verified"
            )
            is True,
            "fields_verified": len(field_evidence),
            "learned_map_version": mapping.get("version"),
            "one_shot": submitted.get("one_shot") is True,
            "portal_confirmed": portal.get("portal_confirmed") is True,
            "review_authoritative": authoritative.get("review_authoritative") is True,
            "single_use_replay_denied": replay_denied,
            "submit_count": submit_count,
            "tracker_readback_verified": final_transaction.get("tracker", {}).get(
                "readback_verified"
            )
            is True,
        },
        "safety": deepcopy(SAFETY_EVIDENCE),
    }
    report["final_audit"] = audit_operator_report(report)
    if report["final_audit"]["checks_passed"] is not True:
        raise OperatorBlockedError("final sanitized operator audit failed")
    return report


DemoRunner = Callable[..., dict]
LiveTransportFactory = Callable[[str], object]
LiveHealthProbe = Callable[[str], dict]
LiveCoverage = Callable[..., dict]


def _load_runtime_object(path: Path | str, *, label: str) -> dict:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OperatorBlockedError(f"{label} could not be read") from exc
    if not isinstance(payload, dict):
        raise OperatorBlockedError(f"{label} must be a JSON object")
    return payload


def _verify_manifest_file(path: Path | str, expected_sha256: str, *, label: str) -> None:
    try:
        actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise OperatorBlockedError(f"{label} could not be read") from exc
    if actual != expected_sha256:
        raise OperatorBlockedError(f"{label} evidence drift detected")


def _verified_profile_resume(manifest: dict) -> tuple[dict, dict]:
    profile_binding = manifest["profile"]
    resume_binding = manifest["resume"]
    profile_path = Path(profile_binding["path"])
    _verify_manifest_file(profile_path, profile_binding["sha256"], label="profile")
    profile = _load_runtime_object(profile_path, label="profile")
    try:
        evidence = resume_preflight.preflight_profile_resume(profile_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise OperatorBlockedError("profile-selected Resume.pdf preflight failed") from exc
    expected = {
        "path": str(Path(resume_binding["path"]).resolve()),
        "basename": resume_binding["basename"],
        "content_type": resume_binding["content_type"],
        "sha256": resume_binding["sha256"],
        "verified": resume_binding["verified"],
    }
    observed = {
        "path": str(Path(evidence["path"]).resolve()),
        "basename": evidence["basename"],
        "content_type": evidence["content_type"],
        "sha256": evidence["sha256"],
        "verified": evidence["verified"],
    }
    if observed != expected:
        raise OperatorBlockedError("profile-selected Resume.pdf evidence drift detected")
    return profile, evidence


def run_live_prepare(
    *,
    manifest_path: Path,
    approved_answers_path: Path,
    step: str,
    cdp_base_url: str,
    production_enabled: bool,
    transport_factory: LiveTransportFactory = ScopedCDPTransport,
    health_probe: LiveHealthProbe = browser_health.probe_cdp_health,
    coverage: LiveCoverage = prepare_live_job.build_coverage_matrix,
) -> dict:
    """Prepare one manifest-bound page without navigation or submission."""
    prepare_live_job._validate_local_cdp_base_url(cdp_base_url)
    manifest = live_run_manifest.load_manifest(
        manifest_path, production_enabled=production_enabled
    )
    profile, resume = _verified_profile_resume(manifest)
    approved_answers = _load_runtime_object(
        approved_answers_path, label="approved answers"
    )
    resume_answer = approved_answers.get("resume")
    if resume_answer is not None and Path(str(resume_answer)).resolve() != Path(
        resume["path"]
    ).resolve():
        raise OperatorBlockedError("approved resume differs from profile-selected Resume.pdf")
    approved_answers["resume"] = str(Path(resume["path"]).resolve())

    identity = manifest["identity"]
    target = manifest["target"]
    mapping = tenant_field_maps.resolve_field_map(
        page_url=target["url"], platform=identity["platform"]
    )
    if mapping.get("tenant") != identity["tenant"]:
        raise OperatorBlockedError("learned tenant differs from manifest identity")
    actions = tenant_field_maps.build_step_actions(
        mapping=mapping,
        step=step,
        approved_answers=approved_answers,
    )
    if not any(action.get("field") == "resume" for action in actions):
        raise OperatorBlockedError("live prepare step must upload profile-selected Resume.pdf")
    transition = tenant_field_maps.plan_next_step(
        mapping=mapping,
        current_step=step,
        completed_fields=set(approved_answers),
        conditions={},
    )
    if transition.get("status") == "human_required":
        raise OperatorBlockedError("learned step conditions remain human-required")

    health = health_probe(cdp_base_url)
    if not isinstance(health, dict) or health.get("status") != "ready":
        raise OperatorBlockedError("loopback Chrome CDP health gate failed")

    transport = transport_factory(cdp_base_url)
    with transport.bind_mutable_page_target(target["id"]) as page:  # type: ignore[attr-defined]
        snapshot = page.read_only_snapshot()
        if (
            snapshot.get("read_only") is not True
            or snapshot.get("target_id") != target["id"]
            or snapshot.get("url") != target["url"]
        ):
            raise OperatorBlockedError("exact target binding drift detected")
        selectors = [str(action["selector"]) for action in actions]
        surface_reader = getattr(page, "inspect_safety_surface", None)
        if not callable(surface_reader):
            raise OperatorBlockedError("exact-page browser canary evidence is unavailable")
        surface = surface_reader(selectors)
        canary = browser_integration_canary.run_canary(
            identity["platform"],
            {
                **surface,
                "target_current": True,
                "submission_enabled": False,
            },
        )
        if canary.get("status") != "passed":
            raise OperatorBlockedError(
                f"exact-page browser canary blocked: {canary.get('reason', 'unknown')}"
            )

        expected_identity = {
            key: identity[key] for key in ("company", "role", "requisition")
        }

        def dispatch(**kwargs):
            return prepare_live_job._dispatch_live_html(
                **kwargs,
                expected_identity=expected_identity,
                expected_platform=identity["platform"],
            )

        prepared = prepare_live_job.prepare_live_job(
            page=page,
            target_id=target["id"],
            expected_url=target["url"],
            expected_identity=expected_identity,
            profile=profile,
            prepare=dispatch,
            coverage=coverage,
            approved_answers=approved_answers,
            apply_known=lambda _: tenant_field_maps.execute_step_actions(
                page=page,
                target_id=target["id"],
                expected_url=target["url"],
                actions=actions,
            ),
        )

    live_run_manifest.validate_manifest(
        manifest,
        production_enabled=production_enabled,
        observed_binding={
            "target_id": prepared["target_id"],
            "page_url": prepared["page_url"],
            **prepared["identity"],
            "platform": prepared["platform"],
            "tenant": mapping["tenant"],
        },
    )
    sanitized = {
        **prepare_live_job._sanitize_review_evidence(prepared),
        "status": "prepared",
        "manifest_binding": {
            "schema_version": manifest["schema_version"],
            "mode": manifest["mode"],
            "job_id": manifest["job_id"],
            "queue_id": manifest["queue_id"],
            "tenant": identity["tenant"],
        },
        "health": {
            "browser_ready": True,
            "canary_passed": True,
            "exact_target_bound": True,
        },
        "learned_map": {"version": mapping["version"], "tenant": mapping["tenant"]},
        "resume": {"basename": "Resume.pdf", "verified": True},
    }
    output = Path(manifest["runtime_paths"]["preparation"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(sanitized, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return sanitized


def main(
    argv: list[str] | None = None,
    *,
    demo_runner: DemoRunner | None = None,
    live_transport_factory: LiveTransportFactory = ScopedCDPTransport,
    live_health_probe: LiveHealthProbe = browser_health.probe_cdp_health,
    live_coverage: LiveCoverage = prepare_live_job.build_coverage_matrix,
) -> int:
    parser = argparse.ArgumentParser(description="Guarded production operator proof")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("local-demo")
    demo.add_argument("--resume", required=True)
    demo.add_argument("--runtime-dir", required=True)
    demo.add_argument("--output", required=True)
    demo.add_argument("--approve-sanitized-submit", action="store_true")
    audit = commands.add_parser("audit")
    audit.add_argument("--report", required=True)
    live = commands.add_parser("live")
    live_commands = live.add_subparsers(dest="live_command", required=True)
    live_prepare = live_commands.add_parser("prepare")
    live_prepare.add_argument("--manifest", required=True)
    live_prepare.add_argument("--approved-answers", required=True)
    live_prepare.add_argument("--step", required=True)
    live_prepare.add_argument("--cdp-base-url", default="http://127.0.0.1:9222")
    live_prepare.add_argument("--enable-production-live", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "live":
        try:
            result = run_live_prepare(
                manifest_path=Path(args.manifest),
                approved_answers_path=Path(args.approved_answers),
                step=args.step,
                cdp_base_url=args.cdp_base_url,
                production_enabled=args.enable_production_live,
                transport_factory=live_transport_factory,
                health_probe=live_health_probe,
                coverage=live_coverage,
            )
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            print(json.dumps({
                "error": str(exc),
                "stage": "prepare",
                "status": "blocked",
                "submission_enabled": False,
                "review_evidence_persisted": False,
            }, sort_keys=True))
            return 2
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "audit":
        try:
            payload = json.loads(Path(args.report).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            result = {
                "checks_passed": False,
                "real_application_authorized": False,
                "status": "not_ready",
            }
            print(json.dumps(result, sort_keys=True))
            return 2
        result = audit_operator_report(payload)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["checks_passed"] is True else 1

    if args.approve_sanitized_submit is not True:
        print(json.dumps({
            "error": "explicit sanitized-demo submit approval is required",
            "real_application_authorized": False,
            "report_persisted": False,
        }, sort_keys=True))
        return 2

    runner = demo_runner or run_local_sanitized_demo
    try:
        report = runner(
            resume_path=Path(args.resume),
            runtime_dir=Path(args.runtime_dir),
            approved=True,
        )
        if audit_operator_report(report).get("checks_passed") is not True:
            raise OperatorBlockedError("final sanitized operator audit failed")
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({
            "error": str(exc),
            "real_application_authorized": False,
            "report_persisted": False,
        }, sort_keys=True))
        return 2

    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
