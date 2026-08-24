# Hermes Job Agent

A safety-first local system for discovering, deduplicating, routing, preparing, tracking, and reporting internship applications.

## Components

- `scanner.py` — normalize candidates, detect ATS platforms, check relevance and duplicates, and enforce MAANGO manual-only routing.
- `pipeline.py` — route supported ATS candidates and reject submission records without confirmation evidence.
- `app_queue.py` — persist discovered jobs in SQLite with idempotent URL-based enqueue and explicit state transitions.
- `audit_log.py` — append structured JSONL audit events with recursive sensitive-field redaction.
- `tracker.py` — read the live Google Sheet and append rows with mandatory API read-back verification.
- `notifier.py` — send deterministic Discord alerts.
- `tests/` — behavior and safety tests.
- `fixtures/` — harmless Greenhouse and Workday test pages.

## Test

```bash
python -m pytest tests -q
```

## Safe dry run

```bash
python scanner.py verified-candidates.json --output scan-results.json
python pipeline.py scan-results.json --output pipeline-plan.json
```

`pipeline.py` produces a plan with submission disabled. Real applications are handled by Hermes ATS skills and must satisfy duplicate, MAANGO, CAPTCHA, field-verification, confirmation, tracker, and notification invariants.

## Privacy

Personal profiles, resumes, OAuth credentials, tracker snapshots, and generated runtime artifacts are intentionally excluded from version control.
