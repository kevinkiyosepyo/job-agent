"""Sanitized browser-surface canaries for non-submitting learned ATS executors."""
from __future__ import annotations


SUPPORTED_PLATFORMS = frozenset({"njoyn", "workday", "greenhouse", "lever", "oracle"})


def run_canary(platform: str, surface: dict[str, object]) -> dict[str, str | bool]:
    """Reject unsafe visual/native surfaces without browser or desktop mutation."""
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError("unsupported canary platform")
    if surface.get("submission_enabled") is not False:
        raise ValueError("canary requires submission_enabled: false")
    retina_scale = surface.get("retina_scale")
    checks = (
        (not isinstance(retina_scale, (int, float)) or retina_scale <= 0, "invalid_retina_scale"),
        (surface.get("target_current") is not True, "stale_focus"),
        (surface.get("control_visible") is not True, "hidden_control"),
        (surface.get("overlay_present") is not False, "overlay_present"),
        (surface.get("native_window_detected") is not False, "unexpected_native_window"),
    )
    for blocked, reason in checks:
        if blocked:
            return {"platform": platform, "status": "blocked", "reason": reason, "submission_enabled": False}
    return {"platform": platform, "status": "passed", "submission_enabled": False}
