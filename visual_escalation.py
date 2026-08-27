"""Universal bounded DOM/AX-to-scoped-OCR escalation contract.

This policy never drives the desktop. A caller supplies exact-page DOM/AX action,
scoped screenshot/OCR, and one inspected page retry seams. OCR is observational
only: it can inform the retry but cannot authorize raw desktop input.
"""
from __future__ import annotations

from collections.abc import Callable


ActionEvidence = dict[str, object]
ScopedOCREvidence = dict[str, object]


def execute_with_scoped_ocr_escalation(
    dom_ax_attempt: Callable[[], ActionEvidence],
    scoped_screenshot_ocr: Callable[[str], ScopedOCREvidence],
    inspected_retry: Callable[[ScopedOCREvidence], ActionEvidence],
) -> dict[str, object]:
    """Try DOM/AX once, inspect one scoped image on failure, then retry once.

    The returned stable blocker prevents repeated visual or input attempts after
    the single inspected retry. The supplied OCR seam must attest to a non-empty
    exact-page scope; otherwise the escalation fails closed without retrying.
    """
    first = dom_ax_attempt()
    if first.get("verified") is True:
        return {
            "status": "completed",
            "dom_ax_attempts": 1,
            "scoped_screenshot_ocr_attempts": 0,
            "inspected_retries": 0,
            "evidence": first.get("evidence"),
        }
    if first.get("verified") is not False:
        return {
            "status": "blocked",
            "blocker": "DOM/AX attempt was not verified",
            "dom_ax_attempts": 1,
            "scoped_screenshot_ocr_attempts": 0,
            "inspected_retries": 0,
        }

    reason = str(first.get("reason", "DOM/AX action was not verified"))
    ocr_evidence = scoped_screenshot_ocr(reason)
    scope = ocr_evidence.get("scope")
    if not isinstance(scope, str) or not scope.strip():
        return {
            "status": "blocked",
            "blocker": "scoped screenshot/OCR evidence requires an exact-page scope",
            "dom_ax_attempts": 1,
            "scoped_screenshot_ocr_attempts": 1,
            "inspected_retries": 0,
        }

    retry = inspected_retry(ocr_evidence)
    if retry.get("verified") is True:
        return {
            "status": "completed",
            "dom_ax_attempts": 1,
            "scoped_screenshot_ocr_attempts": 1,
            "inspected_retries": 1,
            "evidence": retry.get("evidence"),
        }
    return {
        "status": "blocked",
        "blocker": retry.get("reason", "inspected retry was not verified"),
        "dom_ax_attempts": 1,
        "scoped_screenshot_ocr_attempts": 1,
        "inspected_retries": 1,
    }
