# Hermes Job Agent

A safety-first local system for discovering, deduplicating, routing, preparing, tracking, and reporting internship applications.

## Components

- `scanner.py` — normalize candidates, detect ATS platforms, check relevance and duplicates, and enforce MAANGO manual-only routing.
- `pipeline.py` — route supported ATS candidates and reject submission records without confirmation evidence.
- `orchestrator.py` — dry-run CLI that scans verified candidates, routes them, stages supported jobs into the local queue, and writes an audit-backed report.
- `setup_diagnostics.py` — offline readiness checks for profile, resume, Google Sheets OAuth, and optional browser/CDP access.
- `browser_health.py` — probe a local Chrome DevTools endpoint, classify recoverable CDP failures, and emit machine-readable health JSON.
- `browser_actions.py` — deterministic browser-action contracts for text replacement, native-option selection, radio/checkbox state changes, and CDP file attachment; each requires exact post-action read-back evidence before an action is considered verified.
- `sources.py` — bounded-retry adapters plus a token-driven CLI for public Greenhouse and Lever job APIs that normalize active internship candidates into a deterministic JSON artifact.
- `app_queue.py` — persist discovered jobs in SQLite with idempotent URL-based enqueue and explicit state transitions.
- `audit_log.py` — append structured JSONL audit events with recursive sensitive-field redaction.
- `tracker.py` — read the live Google Sheet, append rows with mandatory API read-back verification, and run a self-cleaning integration check.
- `notifier.py` — send deterministic Discord alerts.
- `submission_artifacts.py` — build sanitized submission-evidence artifacts that reconcile verified tracker rows with Discord applied notifications.
- `discord_controls.py` — enforce job-ID-bound approve/reject/retry/skip actions against the local SQLite queue with a machine-readable CLI.
- `tests/` — behavior and safety tests.
- `fixtures/` — harmless Greenhouse, Workday, and Lever test pages.
- `lever_handler.py` — fixture-driven Lever application inspector with field inventory, upload read-back verification, manual-gate detection, confirmation validation, and a machine-readable CLI.
- `greenhouse_handler.py` — fixture-driven Greenhouse application inspector with field inventory, resume read-back, manual-gate plumbing, and confirmation validation.
- `workday_handler.py` — executable Workday listing/application inspector with wizard inventory, resume read-back, parsed-resume mismatch detection, save-draft awareness, multi-gate fail-closed output, and confirmation-reference extraction.
- `oracle_handler.py` — Oracle Recruiting inspector with combobox validation, issue navigation, resume read-back, and confirmation validation.
- `production_readiness.py` — read-only final audit of persisted idempotent dry-run and non-submitting Greenhouse, Workday, Lever, and Oracle fixture evidence.

## Test

```bash
python -m pytest tests -q
```

## Safe dry run

```bash
python orchestrator.py verified-candidates.json --output orchestrator-report.json --source-report sources-report.json
```

`orchestrator.py` runs scanner + pipeline in `dry_run` mode, persists supported jobs into the local SQLite queue as `discovered`, and appends a redacted audit event. Real applications are handled by Hermes ATS skills and must satisfy duplicate, MAANGO, CAPTCHA, field-verification, confirmation, tracker, and notification invariants.

## Production-readiness audit

```bash
python production_readiness.py --dry-run-report runtime/production-run/report.json --fixture-flows runtime/fixture-flows.json
```

The audit is read-only and returns `ready_for_human_gated_production` only when persisted evidence proves idempotent, non-submitting dry-run behavior and all four supported ATS fixture flows remained non-submitting. It explicitly preserves human-only gates: CAPTCHA, email/identity verification, assessments, unknown required questions, and explicit submission authorization.

## Queue-bound Discord controls

```bash
python discord_controls.py job:42:approve --queue-db runtime/production-run/app_queue.sqlite3
```

`discord_controls.py` accepts only job-ID-bound control IDs (`job:<id>:<action>`) and fails if the referenced queue job is missing or currently in the wrong state for that action. Supported actions are:

- `approve` / `reject` for `pending_approval` jobs;
- `retry` / `skip` for `pending_question` and `pending_captcha` jobs.

On success it emits machine-readable JSON describing the applied action, the resolved status (`approved`, `rejected`, `retried`, or `skipped`), and the updated queue record. The Discord integration may bind commands to durable, actor-specific single-use control tokens; a token is valid only for its exact control and actor before its expiry, and replay/expired-token denials leave the queue unchanged and are audit logged without recording the token.

When `--source-report` is supplied, `orchestrator.py` consumes the JSON sidecar written by `sources.py --report` and fails closed before any queue, audit, or output side effects unless `source_health_status` is exactly `healthy`. Malformed sidecars are rejected with stable reasons: `Invalid source report: unreadable`, `Invalid source report: invalid_json`, `Invalid source report: invalid_schema`, `Invalid source report: missing_source_health_status`, `Invalid source report: invalid_source_health_status`, or `Invalid source report: inconsistent_source_health` when the payload claims `healthy` while still reporting failures, sets aggregate stale/freshness-unknown flags, claims aggregate freshness metadata on an empty `source_runs` list, omits any required aggregate evidence (`source_runs`, `freshness_summary`, or `freshness_buckets`), contains malformed top-level `failures` entries (missing/blank `source`, `token`, or `error`), contains malformed top-level aggregate freshness metadata (`stale_result` / `freshness_unknown` must be booleans when present, `warning` must be a string when present, and `latest_posting_at` must be a parseable ISO-8601 timestamp string when present), contains malformed healthy `source_runs` entries (missing/blank `source` or `token`, non-`ok` status, negative/non-integer candidate counts, non-string warning fields, or non-parseable `latest_posting_at` timestamps), contains malformed `freshness_summary` entries (missing, negative, or non-integer aggregate counts), reports any non-OK `source_runs` entry (for example stale, freshness-unknown, or errored boards), hides a missing per-source `latest_posting_at` inside an otherwise `healthy` payload, provides a contradictory top-level `latest_posting_at` that disagrees with the newest healthy `source_runs[*].latest_posting_at` evidence, a contradictory `freshness_summary` count object, or contradictory `freshness_buckets` token membership.

## Safe source collection

```bash
python sources.py --greenhouse example --lever example --output verified-candidates.json --report sources-report.json
```

This writes a deterministic JSON array of internship candidates gathered from
the supplied public board tokens, normalizes tracking parameters out of URLs,
and deduplicates repeated postings across the configured sources. When
`--report` is supplied, the same machine-readable health/status payload emitted
on stdout is also persisted to disk for downstream automation.

Stdout JSON includes:

- `source_runs`: per-token results showing which configured boards returned
  candidates, returned zero, errored, looked stale by posting timestamp, or
  succeeded without timestamps (`freshness_unknown: true`).
- `freshness_summary`: aggregate counts for `healthy_runs`, `stale_runs`,
  `freshness_unknown_runs`, and `error_runs`.
- `freshness_buckets`: exact `{source, token}` entries in each health bucket
  (`healthy`, `stale`, `freshness_unknown`, `error`).
- `source_health_status`: one top-level status of `healthy`, `partial_error`,
  or `stale_or_unknown` so callers do not need to re-derive precedence rules.

Failure signaling is fail-closed:

- missing timestamps on any successful configured source set top-level
  `freshness_unknown: true`, `stale_result: true`, and an aggregate warning;
- at least one `--greenhouse` or `--lever` token is required or the CLI exits
  `2` with a machine-readable configuration error and no artifact;
- if one token fails, successful candidates are still written, stdout reports a
  `failures` array, and the CLI exits `1`;
- if all configured tokens succeed but yield zero internship candidates, the
  empty artifact is still written, stdout is marked `stale_result: true`, and
  the CLI exits `3`;
- if the newest posting timestamp in a non-empty snapshot is older than 30
  days, stdout is marked `stale_result: true`, includes a freshness warning,
  and exits `3`.

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

## Operations runbook

See `OPERATIONS.md` for the standard operator workflow, incident triage, security review checklist, and release checklist.

## Privacy

Personal profiles, resumes, OAuth credentials, tracker snapshots, and generated runtime artifacts are intentionally excluded from version control.
