"""Authorization-gated, exact-target one-shot submission without replay."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from page_recovery import record_page_action


MANDATORY_HUMAN_GATES = {
    "captcha",
    "assessment",
    "email_verification",
    "identity_verification",
}


class SubmitBlockedError(ValueError):
    """Submission must stop before authorization consumption or page mutation."""


class SubmitInterrupted(RuntimeError):
    """The one allowed submit click may have completed before interruption."""


class AuthorizationStore(Protocol):
    def consume(self, **kwargs) -> dict: ...


class ExactSubmitPage(Protocol):
    def read_only_snapshot(self) -> dict: ...

    def inspect_submit_control(self, selector: str) -> dict: ...

    def click_submit_once(self, selector: str) -> None: ...

    def inspect_confirmation(self) -> dict: ...


def _gate_types(snapshot: dict) -> list[str]:
    gates = snapshot.get("gates", [])
    if not isinstance(gates, list):
        raise SubmitBlockedError("page gates were not safely inventoried")
    result = []
    for gate in gates:
        if isinstance(gate, str):
            result.append(gate.strip().casefold())
        elif isinstance(gate, dict) and isinstance(gate.get("type"), str):
            result.append(gate["type"].strip().casefold())
        else:
            raise SubmitBlockedError("page gates were not safely inventoried")
    return result


def _verify_snapshot(
    snapshot: dict,
    *,
    target_id: str,
    expected_url: str,
    requisition: str,
    maango_approved: bool,
) -> None:
    identity = snapshot.get("identity", {})
    if (
        snapshot.get("read_only") is not True
        or snapshot.get("target_id") != target_id
        or snapshot.get("url") != expected_url
        or not isinstance(identity, dict)
        or identity.get("requisition") != requisition
    ):
        raise SubmitBlockedError("exact target ID, URL, and requisition are required")
    gates = _gate_types(snapshot)
    mandatory = next((gate for gate in gates if gate in MANDATORY_HUMAN_GATES), None)
    if mandatory is not None:
        raise SubmitBlockedError(f"{mandatory} gate blocks submission")
    if gates:
        raise SubmitBlockedError(f"{gates[0]} human gate blocks submission")
    if snapshot.get("maango") is True and maango_approved is not True:
        raise SubmitBlockedError("explicit MAANGO approval is required")


def _verify_control(
    control: dict, *, selector: str, target_id: str, expected_url: str
) -> None:
    if (
        not isinstance(control, dict)
        or control.get("selector") != selector
        or control.get("target_id") != target_id
        or control.get("url") != expected_url
        or control.get("visible") is not True
        or control.get("enabled") is not True
        or control.get("unique") is not True
        or control.get("role") != "button"
    ):
        raise SubmitBlockedError("submit control must be one exact visible, enabled, unique button")


def _blocked_after_consumption(blocker: str) -> dict[str, object]:
    return {
        "status": "blocked",
        "blocker": blocker,
        "next_action": "inspect_confirmation_without_replay",
        "authorization_consumed": True,
        "one_shot": True,
        "replay_allowed": False,
    }


def execute_one_shot_submit(
    *,
    authorization_store: AuthorizationStore,
    token: str,
    page: ExactSubmitPage,
    journal_path: Path,
    job_id: int,
    target_id: str,
    expected_url: str,
    requisition: str,
    review_evidence_sha256: str,
    actor: str,
    now: str,
    submit_selector: str,
    maango_approved: bool = False,
) -> dict[str, object]:
    """Consume authorization, journal intent, click once, then only inspect."""
    snapshot = page.read_only_snapshot()
    _verify_snapshot(
        snapshot,
        target_id=target_id,
        expected_url=expected_url,
        requisition=requisition,
        maango_approved=maango_approved,
    )
    _verify_control(
        page.inspect_submit_control(submit_selector),
        selector=submit_selector,
        target_id=target_id,
        expected_url=expected_url,
    )
    authorization_store.consume(
        token=token,
        current_binding={
            "job_id": job_id,
            "target_id": target_id,
            "page_url": expected_url,
            "requisition": requisition,
            "review_evidence_sha256": review_evidence_sha256,
        },
        actor=actor,
        now=now,
    )
    intent_evidence = {
        "status": "intent_recorded",
        "verified": False,
        "job_id": job_id,
        "target_id": target_id,
        "page_url": expected_url,
        "requisition": requisition,
        "review_evidence_sha256": review_evidence_sha256,
        "selector": submit_selector,
    }
    record_page_action(Path(journal_path), action="submit", evidence=intent_evidence)

    try:
        _verify_snapshot(
            page.read_only_snapshot(),
            target_id=target_id,
            expected_url=expected_url,
            requisition=requisition,
            maango_approved=maango_approved,
        )
        _verify_control(
            page.inspect_submit_control(submit_selector),
            selector=submit_selector,
            target_id=target_id,
            expected_url=expected_url,
        )
    except SubmitBlockedError:
        return _blocked_after_consumption("target or submit control changed after authorization")

    try:
        page.click_submit_once(submit_selector)
    except SubmitInterrupted:
        confirmation = page.inspect_confirmation()
        if not isinstance(confirmation, dict) or confirmation.get("confirmed") is not True:
            return _blocked_after_consumption("submit interrupted without confirmation")
        record_page_action(
            Path(journal_path),
            action="submit",
            evidence={
                **intent_evidence,
                "status": "confirmation_observed_after_interruption",
                "verified": True,
            },
        )
        return {
            "status": "confirmation_observed",
            "authorization_consumed": True,
            "one_shot": True,
            "replay_allowed": False,
            "recovered_by_inspection": True,
        }

    confirmation = page.inspect_confirmation()
    if not isinstance(confirmation, dict) or confirmation.get("confirmed") is not True:
        return _blocked_after_consumption("submit completed without confirmation")
    record_page_action(
        Path(journal_path),
        action="submit",
        evidence={
            **intent_evidence,
            "status": "confirmation_observed",
            "verified": True,
        },
    )
    return {
        "status": "confirmation_observed",
        "authorization_consumed": True,
        "one_shot": True,
        "replay_allowed": False,
    }
