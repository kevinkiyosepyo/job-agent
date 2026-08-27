"""Non-submitting exact-target live preparation orchestration.

The command seam deliberately accepts an already bound page adapter. It never
navigates, submits, reaches credentials, tracker, or notification services. Its
only durable result is sanitized Review-ready evidence.
"""
from __future__ import annotations

from typing import Callable, Protocol


class ReadOnlyLivePage(Protocol):
    target_id: str

    def read_only_snapshot(self) -> dict[str, object]: ...


class LivePreparationError(ValueError):
    """Live preparation cannot safely proceed without exact identity evidence."""


Prepare = Callable[..., dict]
Coverage = Callable[..., dict]


def _identity(payload: dict) -> dict[str, str]:
    return {key: str(payload.get(key, "")) for key in ("company", "role", "requisition")}


def prepare_live_job(
    *,
    page: ReadOnlyLivePage,
    target_id: str,
    expected_url: str,
    expected_identity: dict[str, str],
    profile: dict,
    prepare: Prepare,
    coverage: Coverage,
) -> dict:
    """Inspect one fresh exact target and emit non-submitting Review evidence."""
    snapshot = page.read_only_snapshot()
    if snapshot.get("read_only") is not True or snapshot.get("target_id") != target_id:
        raise LivePreparationError("exact trusted target binding is required")
    if snapshot.get("url") != expected_url:
        raise LivePreparationError("target URL changed before live preparation")
    html = snapshot.get("html")
    if not isinstance(html, str):
        raise LivePreparationError("exact target did not return sanitized HTML evidence")

    prepared = prepare(html_text=html, page_url=expected_url)
    identity = _identity(prepared)
    expected = {key: str(expected_identity.get(key, "")) for key in identity}
    if identity != expected:
        raise LivePreparationError("company, role, or requisition changed before live preparation")
    if prepared.get("submission_enabled") is not False:
        raise LivePreparationError("live preparation must remain non-submitting")

    questions = prepared.get("questions", [])
    if not isinstance(questions, list):
        raise LivePreparationError("handler returned invalid question inventory")
    answer_coverage = coverage(profile=profile, questions=questions, company=identity["company"])
    review_ready = not answer_coverage.get("human_required")
    return {
        "target_id": target_id,
        "page_url": expected_url,
        "identity": identity,
        "platform": prepared.get("platform", ""),
        "submission_enabled": False,
        "review_ready": review_ready,
        "answer_coverage": answer_coverage,
        "evidence": {"sanitized": True, "target_bound": True},
    }
