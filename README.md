# Hermes Job Agent

A safety-first local system for discovering, deduplicating, routing, preparing, tracking, and reporting internship applications.

## Components

- `scanner.py` — normalize candidates, detect ATS platforms, check relevance and duplicates, and enforce MAANGO manual-only routing.
- `pipeline.py` — route supported ATS candidates and reject submission records without confirmation evidence.
- `orchestrator.py` — dry-run CLI that scans verified candidates, routes them, stages supported jobs into the local queue, and writes an audit-backed report.
- `setup_diagnostics.py` — offline readiness checks for profile, resume, Google Sheets OAuth, and optional browser/CDP access.
- `browser_health.py` — probe a local Chrome DevTools endpoint, classify recoverable CDP failures, and emit machine-readable health JSON.
- `sources.py` — bounded-retry adapters for public Greenhouse and Lever job APIs that normalize active internship candidates.
- `app_queue.py` — persist discovered jobs in SQLite with idempotent URL-based enqueue and explicit state transitions.
- `audit_log.py` — append structured JSONL audit events with recursive sensitive-field redaction.
- `tracker.py` — read the live Google Sheet, append rows with mandatory API read-back verification, and run a self-cleaning integration check.
- `notifier.py` — send deterministic Discord alerts.
- `tests/` — behavior and safety tests.
- `fixtures/` — harmless Greenhouse and Workday test pages.

## Test

```bash
python -m pytest tests -q
```

## Safe dry run

```bash
python orchestrator.py verified-candidates.json --output orchestrator-report.json
```

`orchestrator.py` runs scanner + pipeline in `dry_run` mode, persists supported jobs into the local SQLite queue as `discovered`, and appends a redacted audit event. Real applications are handled by Hermes ATS skills and must satisfy duplicate, MAANGO, CAPTCHA, field-verification, confirmation, tracker, and notification invariants.

## Browser/CDP health check

```bash
python browser_health.py --base-url http://127.0.0.1:9222
```

Exit code `0` means the endpoint is ready for automation. Exit code `1` means the issue is recoverable and the JSON payload includes a stable `error_code` such as `connection_refused` or `no_page_targets`.

## Offline setup diagnostics

```bash
python setup_diagnostics.py --skip-browser
```

This command validates the local `profile.json`, confirms that `resume.primary` points to a real file, checks that the Google Sheets write token exists, and can optionally skip the live browser probe when you only want offline readiness checks. Exit code `0` means every required offline prerequisite is ready.

## Tracker integration smoke test

```bash
python tracker.py integration-check --tag local-smoke
```

This command snapshots the current tracking rows, appends one clearly-marked test row, verifies the append via fresh read-back, and then rewrites the original rows with a blank tail row so the smoke-test data is cleaned up.

## Privacy

Personal profiles, resumes, OAuth credentials, tracker snapshots, and generated runtime artifacts are intentionally excluded from version control.
