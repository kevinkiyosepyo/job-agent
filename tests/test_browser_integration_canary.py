from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.mark.parametrize("platform", ["njoyn", "workday", "greenhouse", "lever", "oracle"])
def test_browser_canary_accepts_sanitized_exact_target_surface(platform: str):
    import browser_integration_canary

    result = browser_integration_canary.run_canary(
        platform,
        {
            "retina_scale": 2.0,
            "target_current": True,
            "control_visible": True,
            "overlay_present": False,
            "native_window_detected": False,
            "submission_enabled": False,
        },
    )

    assert result == {"platform": platform, "status": "passed", "submission_enabled": False}


@pytest.mark.parametrize(
    ("surface", "expected_reason"),
    [
        ({"retina_scale": 0}, "invalid_retina_scale"),
        ({"target_current": False}, "stale_focus"),
        ({"control_visible": False}, "hidden_control"),
        ({"overlay_present": True}, "overlay_present"),
        ({"native_window_detected": True}, "unexpected_native_window"),
    ],
)
def test_browser_canary_blocks_visual_or_native_window_hazards(surface: dict[str, object], expected_reason: str):
    import browser_integration_canary

    baseline = {
        "retina_scale": 2.0,
        "target_current": True,
        "control_visible": True,
        "overlay_present": False,
        "native_window_detected": False,
        "submission_enabled": False,
    }
    baseline.update(surface)

    assert browser_integration_canary.run_canary("njoyn", baseline) == {
        "platform": "njoyn",
        "status": "blocked",
        "reason": expected_reason,
        "submission_enabled": False,
    }
