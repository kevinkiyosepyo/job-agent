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
- `mutable_cdp_page_adapter.py` — mutable exact-target CDP field adapter for sanitized/local preparation. It supports only visible, enabled text, native-select, checked-control, and file-input operations with fresh URL checks and post-operation read-back seams; it deliberately exposes no navigation, desktop input, coordinates, or hidden-control mutation.
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
- `prepare_live_job.py` — guarded exact-target, non-submitting live-preparation CLI and seam. The production CLI accepts only a loopback CDP origin, freshly binds the requested page target, requires exact URL/company/role/requisition/platform/learned-step evidence, dispatches the ATS handler, runs answer coverage, and resolves explicit semantic answers through a versioned tenant map. Every field must pass post-action read-back before the command persists a Review-ready bundle; persisted evidence retains semantic field/selector verification but strips profile and answer values.
- `tenant_field_maps.py` — versioned exact-host/path learned controls and conditional steps for sanitized Greenhouse, Workday, Lever, Oracle, and Njoyn tenants. Semantic keys map to one allowlisted operation/selector; raw selectors, unknown tenants/steps, missing observed controls, unsupported combobox mutation, credential fields, and unmet parser/question/Review conditions fail closed. `prepare_live_job.py` uses this registry by default rather than rediscovering controls.
- `review_reconciler.py` — pure authoritative-Review reconciler. It compares both prepared and server-rendered target identity, every supplied profile field, the exact `Resume.pdf` basename/content hash, required parser repairs, and required-question read-back. Any difference is retained as a sanitized `human_required` blocker; an all-exact artifact receives a canonical SHA-256 for later approval binding but explicitly carries `submission_authorized: false`.
- `submission_authorization.py` — local SQLite store for expiring, single-use submission authorization. Issuance recomputes and verifies an authoritative Review artifact hash, binds job ID/target ID/URL/requisition/hash/actor, and stores only a SHA-256 token digest. Consumption is atomic; replay and expiry fail closed, while any target or Review drift permanently invalidates the authorization before a submit action can run.
- `one_shot_submit.py` — irreversible one-shot submit coordinator over a deliberately narrow exact-page protocol. It blocks mandatory human gates and unapproved MAANGO before token consumption, verifies one visible/enabled/unique submit button, consumes exact-bound authorization, journals intent before one scoped click, and thereafter permits confirmation inspection only. Interruption or missing confirmation can never route back to a second click.
- `confirmation_reconciliation.py` — two-source learned-ATS submission proof for Greenhouse, Workday, Lever, Oracle, and Njoyn. A platform handler must first classify sanitized HTML as confirmation; then candidate-home/application-list evidence must contain exactly one matching platform/company/role/requisition record with both `state: submitted` and `submitted: true`. Requisition, identity, state, and ambiguity drift remain explicit blockers; raw HTML is replaced by a SHA-256.
- `post_submit_transaction.py` — durable per-job portal → tracker/read-back → Discord/read-back coordinator with no submit API. It atomically records an attempt claim before either downstream side effect, hashes rather than persists tracker/message payloads, blocks Discord until exact tracker read-back, and completes only after exact Discord read-back. Partial failures resume by read-back only, preventing duplicate tracker rows or messages.
- `local_cdp_operator.py` — real local Chrome-for-Testing integration harness for the sanitized `fixtures/local_operator_e2e.html` page. It launches one ephemeral headless process, communicates only through dedicated CDP pipe descriptors, freshly discovers and attaches one exact page target, and exposes bounded fixture-only Review/submit/confirmation observations. The integration covers Retina rendering, overlay rejection, scoped screenshot/OCR observation, interrupted-submit recovery, restart, and stale-target rejection without a network listener or production data.
- `production_operator.py` — single approval-gated operator proof CLI. Its `local-demo` command composes all seven exact learned Greenhouse controls, authoritative Review, an expiring single-use authorization, one-shot fixture submit, learned-handler confirmation, candidate-portal reconciliation, and local-only tracker/Discord read-backs. It persists only health booleans, PII-free timing, sanitized evidence counts, and a recomputed final audit. There is deliberately no real-application command or production downstream adapter.
- `session_gate.py` — validates a tenant’s runtime-only session reference and returns either authenticated-session reuse or an explicit human login/identity-verification gate; it never receives or serializes credentials.
- `tenant_metadata.py` — loads versioned learned-tenant records only after matching the page hostname, ATS platform, and tenant identity; it returns a secret-free runtime-only session reference or fails closed.
- `browser_integration_canary.py` — sanitised non-mutating canaries for Njoyn, Workday, Greenhouse, Lever, and Oracle that fail closed on invalid Retina scale, stale target focus, hidden controls, overlays, or unexpected native windows while requiring submission to remain disabled.
- `timing_telemetry.py` — emits PII-free elapsed-second evidence for discovery, login, upload, form fill, parser repair, Review, confirmation, tracker read-back, and Discord read-back.
- `production_readiness.py` — read-only final audit of persisted idempotent dry-run, canary, and non-submitting Greenhouse, Workday, Lever, and Oracle fixture evidence, plus optional learned CGI/Njoyn speed evidence. When canary evidence is supplied it requires passing, disabled-submission results for Njoyn, Workday, Greenhouse, Lever, and Oracle; the optional benchmark requires preparation in under five minutes and fully verified submission in under ten minutes while preserving parser-repair, Review, confirmation, tracker-read-back, Discord-read-back, and disabled-submission invariants.

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

## Guarded live preparation

Keep the approved-answer map and generated evidence under ignored `runtime/`. After independently reading the current page target ID and exact identity, run:

```bash
python prepare_live_job.py \
  --target-id '<exact-page-target-id>' \
  --expected-url 'https://sanitized.example.test/apply/REQ-123' \
  --company 'Sanitized Example' \
  --role 'Software Engineer Intern' \
  --requisition 'REQ-123' \
  --platform 'greenhouse' \
  --step 'application' \
  --profile runtime/sanitized-profile.json \
  --approved-answers runtime/approved-answers.json \
  --output runtime/review-evidence.json
```

The approved-answer file uses semantic learned keys such as `first_name`, never CSS selectors. The command never navigates or submits. A changed target/URL, unsupported or gated ATS surface, unknown tenant/step/key, identity or handler-platform mismatch, unmet conditional step, or failed field read-back exits nonzero without writing Review evidence.

Authoritative Review is a separate step. `review_reconciler.reconcile_review(...)` must receive a fresh server-rendered Review inventory, independently derived profile/resume facts, required parser-repair fields, required-question IDs, and the exact expected target. Only `review_authoritative: true` with an empty `human_required` list can be presented for Task 4 approval; it is never itself permission to submit.

Submission authorization is issued through `SubmissionAuthorizationStore` only after that canonical Review hash is independently recomputed. Keep the returned opaque token runtime-only. It is actor-bound, expires at the stated instant, can be consumed once, and is permanently invalidated if the current job ID, target ID, URL, requisition, or Review hash differs.

`execute_one_shot_submit(...)` is the only submit coordinator. It requires the exact page seam to re-read target and submit-control evidence immediately before the one click. A CAPTCHA, assessment, email/identity gate, unapproved MAANGO job, target/control drift, interruption, or missing confirmation stops the flow; once authorization is consumed, recovery is confirmation inspection without replay.

After any observed confirmation, `extract_confirmation(...)` must verify it through the matching learned ATS handler and `reconcile_candidate_portal(...)` must independently read back one exact submitted application record. Only `portal_confirmed: true` and `safe_for_post_submit: true` may enter the tracker/notification transaction; a success-looking page alone is insufficient.

`PostSubmitTransactionCoordinator` then enforces tracker append plus exact read-back before Discord send plus exact read-back. Its stable per-job state hashes portal/tracker/message inputs and claims each side effect once. An attempted-but-unverified stage can only be resumed by read-back; a changed payload or portal artifact is rejected instead of spawning a duplicate transaction.

## Sanitized real-Chrome integration proof

```bash
python -m pytest tests/test_local_cdp_operator.py -q
```

This test launches an installed local Chrome-for-Testing binary with an ephemeral profile and CDP pipe transport, opens only the repository's marker-checked static fixture, and runs the complete guarded preparation → Review → authorization → one-shot submit → confirmation → portal → local tracker/Discord-read-back flow. It deliberately simulates a post-click interruption and then reattaches the exact target; the submit counter must remain one. It also proves overlay blocking, Retina scaling, observation-only scoped screenshot escalation, and stale-URL rejection. All identities, answers, resume bytes, and downstream adapters are sanitized and local.

## Production operator proof and final audit

```bash
python production_operator.py local-demo \
  --resume runtime/sanitized-demo/Resume.pdf \
  --runtime-dir runtime/operator-demo \
  --output runtime/operator-demo/report.json \
  --approve-sanitized-submit
python production_operator.py audit --report runtime/operator-demo/report.json
```

The approval flag applies only to the marker-checked static fixture. Before its local submit, the command requires exact Chrome/CDP target health, a passing Retina canary, no mandatory gate or MAANGO routing, exact `Resume.pdf` preflight, all seven learned-map read-backs, and authoritative Review. The report contains no answer values, authorization token, local path, HTML, tracker payload, or Discord message. Preparation must remain below 300 seconds and verified local submission below 600 seconds. A successful final audit returns `ready_for_manual_live_authorization_review` while keeping `real_application_authorized: false`; it is readiness evidence, never live submission authority.

## Unified live-run manifest

`live_run_manifest.py` defines the closed v1 runtime contract used by the unified CLI work. It binds one mode, job/queue ID, exact target ID/URL, company, role, requisition, learned platform/tenant, verified profile and exact `Resume.pdf` hashes, explicit manual-gate state, and unique absolute runtime artifact paths. Unknown or missing fields and observed identity drift fail closed. A `production_live` manifest is inert unless the caller separately passes explicit production enablement; setting the mode inside the manifest cannot enable itself.

The first unified stage is non-submitting preparation:

```bash
python production_operator.py live prepare \
  --manifest runtime/live-run/manifest.json \
  --approved-answers runtime/live-run/approved-answers.json \
  --step application \
  --cdp-base-url http://127.0.0.1:9222
```

It never chooses a tab: the exact target ID comes from the manifest. Before any mapped field action it verifies loopback CDP health, the current target/URL and job identity, the learned tenant and step, answer coverage, visible/unobscured controls, and profile-selected `Resume.pdf` bytes. The result at the manifest's `runtime_paths.preparation` contains identifiers, verified field evidence, and gate booleans only; answer values and local paths are removed. Production manifests additionally require `--enable-production-live`; sanitized/local development does not use that flag.

After the ATS is visibly on its learned Review surface, extract and reconcile it separately:

```bash
python production_operator.py live review \
  --manifest runtime/live-run/manifest.json \
  --approved-answers runtime/live-run/approved-answers.json \
  --step application \
  --required-question work_authorization
```

The command freshly rebinds and revalidates the exact page, reads only a learned platform Review seam (falling back to conservative versioned-map observation), and compares it with the prior preparation, explicit approved answers, and exact resume evidence. Stdout contains only the Review hash, verified field identifiers, blockers, and exact job identity. The persisted `runtime_paths.review` wrapper is likewise value-free. Missing server resume hashes, parser repairs, required-question evidence, or tenant readers remain blockers; Review authority is still not submit authority.

Issue a short-lived authorization only after independently checking that output:

```bash
python production_operator.py live authorize \
  --manifest runtime/live-run/manifest.json \
  --actor '<explicit-operator-identity>' \
  --approve-review-hash '<exact-review-sha256>' \
  --expires-in-seconds 300
```

Expiry is explicit and capped at 600 seconds. MAANGO runs require both `manual_gate.maango_approved: true` in the manifest and `--approve-maango` at authorization time. The opaque single-use token is never printed: it is written once with mode `0600` to `runtime_paths.authorization_handoff`; the authorization database stores only its digest. An existing handoff, Review/job drift, any blocker, a mismatched hash, or uncleared manual gate stops issuance.

Submit only through the one-shot stage, repeating the Review inputs so authority is freshly recomputed on the rebound target:

```bash
python production_operator.py live submit \
  --manifest runtime/live-run/manifest.json \
  --approved-answers runtime/live-run/approved-answers.json \
  --step application \
  --required-question work_authorization \
  --actor '<same-operator-identity>'
```

Immediately before consumption and again before the sole DOM activation, this stage verifies loopback health, exact target/URL/job/tenant identity, page gates and MAANGO state, the visible/enabled/unique learned submit button, and a newly reconciled Review hash equal to the approved hash. Submit intent is written to `runtime_paths.submit_journal` before the click. Once consumed, the raw-token handoff is removed; interruption or missing confirmation always returns `inspect_confirmation_without_replay`. Even an observed confirmation remains unreconciled until the next stage, and this command has no tracker or notification path.

Reconcile confirmation without replay:

```bash
python production_operator.py live confirmation \
  --manifest runtime/live-run/manifest.json
```

The stage requires exact submit-journal evidence, rebinds only the manifest target, validates confirmation through the matching learned ATS handler, and calls the verified `(platform, tenant)` Candidate Home reader. Njoyn, Workday, Greenhouse, Lever, and Oracle are registered. Exactly one matching company/role/requisition record must report both `state: submitted` and `submitted: true`. The sanitized result is written to `runtime_paths.confirmation`; raw HTML and portal payloads are not. An unavailable tenant reader, uncertain confirmation, identity/state mismatch, or duplicate match becomes `human_required` and remains unsafe for post-submit delivery.

For a sanitized/local run, verify the downstream transaction with local adapters:

```bash
python production_operator.py live deliver \
  --manifest runtime/live-run/manifest.json \
  --submitted-date 2026-08-27
```

Delivery requires the exact portal-confirmed artifact. The durable coordinator performs tracker lookup/append/authenticated read-back before Discord lookup/send/authenticated read-back, with one stable transaction ID and separate payload/message hashes. Sanitized mode forbids `--commit-external` and uses local adapters. A `production_live` manifest additionally requires `--enable-production-live --commit-external --discord-channel-id '<exact-channel-id>'`; the Discord token is fetched at call time from the named environment variable and is never persisted. `GoogleSheetsTransactionAdapter` and `DiscordTransactionAdapter` independently require the `commit_external` capability, embed idempotency markers, and refuse changed hashes. Partial recovery is read-back-only.

Inspect or safely resume an interrupted run:

```bash
python production_operator.py live status --manifest runtime/live-run/manifest.json
python production_operator.py live resume --manifest runtime/live-run/manifest.json
```

`status` writes the value-free seven-stage report to `runtime_paths.status` and recommends exactly one next action. `resume` can perform only confirmation inspection after submit intent or durable tracker/Discord read-back after a claimed downstream attempt. It never calls prepare, Review, authorization, or submit. An uncertain or already verified submit always has `submit_replay_allowed: false`; missing authorization handoffs and invalid artifacts route to human review instead of token reissuance. Delivery recovery requires the same explicit submitted date and, for production, the same external commit gates.

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
