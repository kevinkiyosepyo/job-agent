"""Sanitized timing telemetry for bounded ATS execution stages."""
from __future__ import annotations


STAGES = frozenset({
    "discovery", "login", "upload", "form_fill", "parser_repair", "review",
    "confirmation", "tracker_readback", "discord_readback",
})


def record_stage(stage: str, elapsed_seconds: float) -> dict[str, str | float]:
    """Produce PII-free duration evidence for one named lifecycle stage."""
    if stage not in STAGES:
        raise ValueError("unsupported telemetry stage")
    if not isinstance(elapsed_seconds, (int, float)) or elapsed_seconds < 0:
        raise ValueError("elapsed seconds must be non-negative")
    return {"stage": stage, "elapsed_seconds": float(elapsed_seconds)}
