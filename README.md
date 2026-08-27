# Hermes Job Agent

A safety-first local system for discovering, deduplicating, routing, preparing, tracking, and reporting internship applications.

## Components

- `scanner.py` — normalize candidates, detect ATS platforms, check relevance and duplicates, and enforce MAANGO manual-only routing.
- `pipeline.py` — route supported ATS candidates and reject submission records without confirmation evidence.
- `orchestrator.py` — dry-run CLI that scans verified candidates, routes them, stages supported jobs into the local queue, and writes an audit-backed report.
- `setup_diagnostics.py` — offline readiness checks for profile, resume, Google Sheets OAuth, and optional browser/CDP access.
- `browser_health.py` — probe a local Chrome DevTools endpoint, classify recoverable CDP failures, and emit machine-readable health JSON.
- `scoped_cdp.py` — exact-target, read-only CDP transport. It first binds a current `type == page` target by its exact ID from `/json/list`, then permits only fixed `Runtime.evaluate` snapshot reads (URL, title, body text, and HTML); it exposes no navigation, input, upload, or desktop-control operations.
- `browser_actions.py` — deterministic browser-action contracts for text replacement, native-option selection, radio/checkbox state changes, CDP file attachment, scroll-and-click, and one-shot submit/confirmation; each requires exact post-action read-back evidence before an action is considered verified.
- `cdp_page_executor.py` — bounded exact-target action executor. It requires a fresh trusted read-only CDP snapshot whose target ID and URL exactly match the requested page before it delegates text replacement or real native-option selection; stale or untrusted state blocks before mutation, and returned evidence includes the verified target binding.
- `visual_escalation.py` — universal bounded visual recovery contract shared by live ATS executors: it performs one verified DOM/AX attempt, then one exact-page scoped screenshot/OCR inspection and one inspected retry, returning a stable blocker rather than using raw desktop input or repeated retries.
- `answer_map_executor.py` — bounded known-page answer-map executor: fills a complete approved map once and returns field-by-field post-fill read-back evidence; a batch is verified only when every field exactly matches.
- `page_recovery.py` — sanitized page-action journal for click/upload/save/submit recovery. It resumes only from verified state and turns an uncertain submit into a confirmation-inspection blocker rather than replaying it.
- `retry_recovery.py` — bounded recovery policy primitive: makes one normal attempt, then one inspection after a recoverable interruption; an inspector-confirmed completion is returned without replaying a potentially submitted action, while a non-confirming inspection returns a stable blocker instead of retrying blindly.
- `credential_adapter.py` — secret-free runtime Keychain-reference contract for approved ATS account flows. It checks only an approved item’s service/account metadata through `security find-generic-password` without `-w`; returned plans contain availability metadata and a `runtime_only` reference, never a password or other secret.
- `sources.py` — bounded-retry adapters plus a token-driven CLI for public Greenhouse and Lever job APIs that normalize active internship candidates into a deterministic JSON artifact.
- `app_queue.py` — persist discovered jobs in SQLite with idempotent URL-based enqueue and explicit state transitions.
- `audit_log.py` — append structured JSONL audit events with recursive sensitive-field redaction.
- `tracker.py` — read the live Google Sheet, append rows with mandatory API read-back verification, and run a self-cleaning integration check.
- `notifier.py` — send deterministic Discord alerts.
- `amazon_sync.py` — read the official Amazon 2027 monitor scripts, dedupe current hits, stage MAANGO-safe `Pending Manual Action` tracker rows, and optionally append verified tracker rows plus idempotent queue entries.
- `submission_artifacts.py` — build sanitized submission-evidence artifacts that reconcile verified tracker rows with Discord applied notifications.
- `discord_controls.py` — enforce job-ID-bound approve/reject/retry/skip actions against the local SQLite queue with a machine-readable CLI.
- `tests/` — behavior and safety tests.
- `fixtures/` — harmless Greenhouse, Workday, Lever, Oracle, and CGI/Njoyn test pages.
- `lever_handler.py` — fixture-driven Lever application inspector with field inventory, upload read-back verification, manual-gate detection, confirmation validation, and a machine-readable CLI.
- `greenhouse_handler.py` — fixture-driven Greenhouse application inspector with field inventory, resume read-back, manual-gate plumbing, and confirmation validation.
- `workday_handler.py` — executable Workday listing/application inspector with wizard inventory, resume read-back, parsed-resume mismatch detection, save-draft awareness, multi-gate fail-closed output, and confirmation-reference extraction.
- `oracle_handler.py` — Oracle Recruiting inspector with combobox validation, issue navigation, resume read-back, and confirmation validation.
- `njoyn_handler.py` — non-mutating CGI/Njoyn surface inspector; inventories listing identity/Apply entrypoints, account email/password controls, privacy-notice acknowledgement controls, employment-disclosure radios, voluntary-disability selects, resume-upload controls with attached-filename read-back verification, explicit parsed-profile mismatch markers, referral parent/child selects, questionnaire controls, and verified confirmation evidence with an exact CGI reference identifier when rendered. It reports parser correction requirements without silently accepting parsed data, verifies that referral source state is a real `Social Media` → `Instagram` selection rather than typed text, and treats account sign-in/profile creation, privacy notices, required employment disclosures, voluntary disability disclosures, parser corrections, incomplete referral selections, and unresolved required questionnaires as fail-closed manual gates until explicitly handled.
- `standard_ats_live_executor.py` — shared non-submitting executor for Workday, Greenhouse, Lever, and Oracle. It validates the handler plan, batches approved known-page answers via exact read-back evidence, and always stops before submit for human Review.
- `njoyn_live_executor.py` — non-submitting CGI/Njoyn execution contract: batches an approved known-page answer map, verifies the handler-plan parser-repair fields through exact read-back, and always returns `stop_before_submit` for human Review.
- `fixture_e2e.py` — non-submitting vertical fixture flows for supported ATSs, including CGI/Njoyn resume attachment verification, parsed-profile review evidence, and sanitized confirmation artifacts. Explicit parsed-profile mismatches emit field-only parser-repair evidence and remain blocked until every required correction is recorded; unrelated recorded correction IDs are explicitly rejected rather than counting toward completion. The flows never submit, write a tracker row, or send a notification.
- `ats_registry.py` / `prepare_job.py` — shared non-submitting dispatcher for Greenhouse, Workday, Lever, Oracle, and CGI/Njoyn saved surfaces. Every payload explicitly carries `submission_enabled: false`; manual-gated and listing surfaces remain fail-closed. `prepare_job.py --tenant-metadata <path>` loads a matching learned tenant record only after hostname/platform validation; it carries only a runtime-only session reference and authenticated-state metadata into the plan, allowing a repeat flow to reuse an already authenticated session without serializing credentials or scheduling account creation.
- `session_gate.py` — validates a tenant’s runtime-only session reference and returns either authenticated-session reuse or an explicit human login/identity-verification gate; it never receives or serializes credentials.
- `tenant_metadata.py` — loads versioned learned-tenant records only after matching the page hostname, ATS platform, and tenant identity; it returns a secret-free runtime-only session reference or fails closed.
- `browser_integration_canary.py` — sanitised non-mutating canaries for Njoyn, Workday, Greenhouse, Lever, and Oracle that fail closed on invalid Retina scale, stale target focus, hidden controls, overlays, or unexpected native windows while requiring submission to remain disabled.
- `timing_telemetry.py` — emits PII-free elapsed-second evidence for discovery, login, upload, form fill, parser repair, Review, confirmation, tracker read-back, and Discord read-back.
- `production_readiness.py` — read-only final audit of persisted idempotent dry-run and non-submitting Greenhouse, Workday, Lever, and Oracle fixture evidence, plus optional learned CGI/Njoyn speed evidence. The optional evidence requires preparation in under five minutes and fully verified submission in under ten minutes while preserving parser-repair, Review, confirmation, tracker-read-back, Discord-read-back, and disabled-submission invariants.

## Test

```bash
python -m pytest tests -q
```

## Safe dry run

```bash
python orchestrator.py verified-candidates.json --output orchestrator-report.json --source-report sources-report.json
python amazon_sync.py --output runtime/amazon-sync-report.json
```

`orchestrator.py` runs scanner + pipeline in `dry_run` mode, persists supported jobs into the local SQLite queue as `discovered`, and appends a redacted audit event. `amazon_sync.py` performs a non-mutating dry run that reads the official Amazon monitor scripts, plans `Pending Manual Action` tracker rows for current Amazon hits, and writes a machine-readable report without touching the tracker or queue unless `--commit` is supplied. Real applications are handled by Hermes ATS skills and must satisfy duplicate, MAANGO, CAPTCHA, field-verification, confirmation, tracker, and notification invariants.

## Production-readiness audit

```bash
python production_readiness.py --dry-run-report runtime/production-run/report.json --fixture-flows runtime/fixture-flows.json --learned-ats-benchmark runtime/njoyn-benchmark.json
```

The audit is read-only and returns `ready_for_human_gated_production` only when persisted evidence proves idempotent, non-submitting dry-run behavior and all four supported ATS fixture flows remained non-submitting. When `--learned-ats-benchmark` is supplied, it additionally requires CGI/Njoyn preparation below 300 seconds and fully verified submission below 600 seconds, while requiring disabled submission/external side effects plus parser-repair, Review, confirmation, tracker-read-back, and Discord-read-back safety evidence. It explicitly preserves human-only gates: CAPTCHA, email/identity verification, assessments, unknown required questions, and explicit submission authorization.

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
