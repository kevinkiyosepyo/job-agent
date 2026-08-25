"""Versioned allowlist for public Greenhouse and Lever source boards."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SUPPORTED_PLATFORMS = frozenset({"greenhouse", "lever"})


def load_registry(path: str | Path) -> dict[str, Any]:
    """Load active approved sources in a deterministic platform/token order."""
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("Unsupported source registry version")
    entries = payload.get("sources")
    if not isinstance(entries, list):
        raise ValueError("Source registry sources must be a list")

    sources: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Source registry entry must be an object")
        platform = entry.get("platform")
        token = entry.get("token")
        if platform not in SUPPORTED_PLATFORMS or not isinstance(token, str) or not token.strip():
            raise ValueError("Source registry entry has unsupported platform or empty token")
        if entry.get("approved") is True:
            sources.append({"platform": platform, "token": token.strip()})
    return {"version": 1, "sources": sorted(sources, key=lambda item: (item["platform"], item["token"]))}
