#!/usr/bin/env python3
"""Durable JSONL execution journal for leased queue attempts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ExecutionJournal:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, *, job_id: int, attempt_count: int, step: str, payload: dict[str, Any]) -> dict[str, Any]:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "job_id": job_id,
            "attempt_count": attempt_count,
            "step": step,
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]

    def entries_for(self, *, job_id: int, attempt_count: int) -> list[dict[str, Any]]:
        return [
            entry
            for entry in self.read_all()
            if entry.get("job_id") == job_id and entry.get("attempt_count") == attempt_count
        ]

    def latest_step(self, *, job_id: int, attempt_count: int) -> dict[str, Any] | None:
        entries = self.entries_for(job_id=job_id, attempt_count=attempt_count)
        if not entries:
            return None
        return entries[-1]
