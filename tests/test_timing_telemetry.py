from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_timing_telemetry_records_only_stage_and_elapsed_seconds():
    import timing_telemetry

    result = timing_telemetry.record_stage("form_fill", 12.5)

    assert result == {"stage": "form_fill", "elapsed_seconds": 12.5}
