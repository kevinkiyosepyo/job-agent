"""Synchronize the Kevin Bible into an ignored local cache without logging PII."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

GAPI = Path.home() / ".hermes/skills/productivity/google-workspace/scripts/google_api.py"
DEFAULT_CACHE_PATH = Path("runtime/kevin-bible-cache.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_google_document(doc_id: str) -> dict:
    """Fetch one Google Doc through the approved read-only Workspace helper."""
    proc = subprocess.run(
        [sys.executable, str(GAPI), "docs", "get", doc_id],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode:
        raise RuntimeError("Kevin Bible fetch failed")
    payload = json.loads(proc.stdout)
    if not isinstance(payload, dict) or payload.get("documentId") != doc_id:
        raise ValueError("Kevin Bible document source is invalid")
    metadata_proc = subprocess.run(
        [sys.executable, str(GAPI), "drive", "get", doc_id],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if metadata_proc.returncode:
        raise RuntimeError("Kevin Bible metadata fetch failed")
    metadata = json.loads(metadata_proc.stdout)
    modified_at = metadata.get("modifiedTime") if isinstance(metadata, dict) else None
    if metadata.get("id") != doc_id or not isinstance(modified_at, str) or not modified_at:
        raise ValueError("Kevin Bible source timestamp is missing")
    payload["modifiedTime"] = modified_at
    payload.setdefault("revisionId", modified_at)
    return payload


def _profile_value(profile: dict, question_key: str) -> object | None:
    if question_key == "graduation_season":
        return profile.get("education", {}).get("graduation_season")
    return None


def _profile_conflicts(profile: dict, answers: list[dict]) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    for entry in answers:
        if not isinstance(entry, dict):
            continue
        key = entry.get("question_key")
        answer = entry.get("answer")
        if not isinstance(key, str) or answer is None:
            continue
        profile_answer = _profile_value(profile, key)
        if profile_answer is not None and str(profile_answer) != str(answer):
            conflicts.append(
                {
                    "question_key": key,
                    "winner": "profile",
                    "discarded_source": "kevin_bible",
                }
            )
    return conflicts


def _answers_from_body(body: object) -> list[dict]:
    """Parse the explicit, bounded answer block from a Docs text export."""
    if not isinstance(body, str):
        return []
    start = body.find("[answers]")
    end = body.find("[/answers]", start + len("[answers]"))
    if start < 0 or end < 0:
        return []
    entries: list[dict] = []
    entry: dict[str, str] = {}
    for raw_line in body[start + len("[answers]") : end].splitlines():
        line = raw_line.strip()
        if line == "---":
            if entry:
                entries.append(entry)
                entry = {}
            continue
        if not line or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        if key in {"question_key", "answer", "company"} and value:
            entry[key] = value
    if entry:
        entries.append(entry)
    if not all(entry.get("question_key") and entry.get("answer") for entry in entries):
        raise ValueError("Kevin Bible answer entries require question_key and answer")
    return entries


def sync(
    *,
    doc_id: str,
    profile: dict,
    cache_path: Path,
    fetch_document: Callable[[str], dict] = fetch_google_document,
    log: Callable[[str], None] | None = None,
    now: str | None = None,
) -> dict:
    """Read a Bible document, persist its private cache, and report precedence conflicts.

    The cache is intentionally local/ignored. Operational log messages contain only
    identifiers and counts, never document text or answers.
    """
    document = fetch_document(doc_id)
    answers = document.get("answers")
    if answers is None:
        answers = _answers_from_body(document.get("body"))
    if not isinstance(answers, list) or not all(isinstance(entry, dict) for entry in answers):
        raise ValueError("Kevin Bible answers must be a list of objects")
    modified_at = document.get("modifiedTime")
    if not isinstance(modified_at, str) or not modified_at:
        raise ValueError("Kevin Bible source timestamp is missing")
    revision_id = document.get("revisionId")
    if not isinstance(revision_id, str) or not revision_id:
        raise ValueError("Kevin Bible revision is missing")
    fetched_at = now or _utc_now()
    conflicts = _profile_conflicts(profile, answers)
    payload = {
        "source": {
            "doc_id": doc_id,
            "revision_id": revision_id,
            "modified_at": modified_at,
            "fetched_at": fetched_at,
        },
        "answers": answers,
        "conflicts": conflicts,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if log is not None:
        log(f"Kevin Bible sync complete: doc_id={doc_id} answers={len(answers)} conflicts={len(conflicts)}")
    return {"source": payload["source"], "conflicts": conflicts, "answer_count": len(answers)}


def main(argv: list[str] | None = None) -> int:
    """Run a read-only sync and emit only a sanitized operational summary."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--profile", type=Path, default=Path("profile.json"))
    parser.add_argument("--cache-path", type=Path, default=DEFAULT_CACHE_PATH)
    args = parser.parse_args(argv)
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    result = sync(
        doc_id=args.doc_id,
        profile=profile,
        cache_path=args.cache_path,
        fetch_document=fetch_google_document,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
