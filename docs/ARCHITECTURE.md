# Architecture

Every module in the repository, grouped by the pipeline stage it serves. This is the detailed technical reference that the [README](../README.md) summarizes.

The organizing principle throughout is **fail-closed**: each component's default behavior is to refuse. Progress requires positive evidence, and ambiguity produces a stable, named blocker rather than a best-effort guess.

---

## Stage 1 — Discovery and routing

| Module | Responsibility |
|---|---|
| `sources.py` | Bounded-retry adapters plus a token-driven CLI for public Greenhouse and Lever job APIs that normalize active internship candidates into a deterministic JSON artifact. |
| `source_registry.py` | Registry of configured source tokens and their platform bindings. |
| `scanner.py` | Normalize candidates, detect ATS platforms, check relevance and duplicates, and enforce MAANGO manual-only routing. |
| `pipeline.py` | Route supported ATS candidates and reject submission records without confirmation evidence. |
| `orchestrator.py` | Dry-run CLI that scans verified candidates, routes them, stages supported jobs into the local queue, and writes an audit-backed report. |
| `posting_qualifications.py` | Parse a posting's stated qualifications for eligibility screening before a submit is spent. |
| `app_queue.py` | Persist discovered jobs in SQLite with idempotent URL-based enqueue and explicit state transitions. |
| `amazon_sync.py` | Read the official Amazon 2027 monitor scripts, dedupe current hits, stage MAANGO-safe `Pending Manual Action` tracker rows, and optionally append verified tracker rows plus idempotent queue entries. |

### Safe source collection

```bash
python sources.py --greenhouse example --lever example --output verified-candidates.json --report sources-report.json
```

Writes a deterministic JSON array of internship candidates gathered from the supplied public board tokens, normalizes tracking parameters out of URLs, and deduplicates repeated postings across the configured sources. When `--report` is supplied, the same machine-readable health/status payload emitted on stdout is also persisted to disk for downstream automation.

Stdout JSON includes:

- `source_runs` — per-token results showing which configured boards returned candidates, returned zero, errored, looked stale by posting timestamp, or succeeded without timestamps (`freshness_unknown: true`).
- `freshness_summary` — aggregate counts for `healthy_runs`, `stale_runs`, `freshness_unknown_runs`, and `error_runs`.
- `freshness_buckets` — exact `{source, token}` entries in each health bucket (`healthy`, `stale`, `freshness_unknown`, `error`).
- `source_health_status` — one top-level status of `healthy`, `partial_error`, or `stale_or_unknown` so callers do not need to re-derive precedence rules.

Failure signaling is fail-closed:

- missing timestamps on any successful configured source set top-level `freshness_unknown: true`, `stale_result: true`, and an aggregate warning;
- at least one `--greenhouse` or `--lever` token is required or the CLI exits `2` with a machine-readable configuration error and no artifact;
- if one token fails, successful candidates are still written, stdout reports a `failures` array, and the CLI exits `1`;
- if all configured tokens succeed but yield zero internship candidates, the empty artifact is still written, stdout is marked `stale_result: true`, and the CLI exits `3`;
- if the newest posting timestamp in a non-empty snapshot is older than 30 days, stdout is marked `stale_result: true`, includes a freshness warning, and exits `3`.

### Safe dry run

```bash
python orchestrator.py verified-candidates.json --output orchestrator-report.json --source-report sources-report.json
python amazon_sync.py --output runtime/amazon-sync-report.json
```

`orchestrator.py` runs scanner + pipeline in `dry_run` mode, persists supported jobs into the local SQLite queue as `discovered`, and appends a redacted audit event. `amazon_sync.py` performs a non-mutating dry run that reads the official Amazon monitor scripts, plans `Pending Manual Action` tracker rows for current Amazon hits, and writes a machine-readable report without touching the tracker or queue unless `--commit` is supplied.

When `--source-report` is supplied, `orchestrator.py` consumes the JSON sidecar written by `sources.py --report` and fails closed before any queue, audit, or output side effects unless `source_health_status` is exactly `healthy`. Malformed sidecars are rejected with stable reasons: `Invalid source report: unreadable`, `invalid_json`, `invalid_schema`, `missing_source_health_status`, `invalid_source_health_status`, or `inconsistent_source_health` when the payload claims `healthy` while still reporting failures, sets aggregate stale/freshness-unknown flags, claims aggregate freshness metadata on an empty `source_runs` list, omits required aggregate evidence (`source_runs`, `freshness_summary`, or `freshness_buckets`), contains malformed `failures` entries (missing/blank `source`, `token`, or `error`), contains malformed aggregate freshness metadata (`stale_result` / `freshness_unknown` must be booleans when present, `warning` a string when present, `latest_posting_at` a parseable ISO-8601 timestamp when present), contains malformed healthy `source_runs` entries (missing/blank `source` or `token`, non-`ok` status, negative/non-integer candidate counts, non-string warning fields, or non-parseable timestamps), contains malformed `freshness_summary` entries, reports any non-OK `source_runs` entry, hides a missing per-source `latest_posting_at` inside an otherwise `healthy` payload, or provides contradictory top-level `latest_posting_at`, `freshness_summary` counts, or `freshness_buckets` token membership.

---

## Stage 2 — Browser control

The browser layer is deliberately built as a series of narrowing capabilities. Read-only transport at the bottom, bounded mutation above it, and no layer that exposes navigation or desktop input.

| Module | Responsibility |
|---|---|
| `browser_health.py` | Probe a local Chrome DevTools endpoint, classify recoverable CDP failures, and emit machine-readable health JSON. |
| `scoped_cdp.py` | Exact-target, read-only CDP transport. Binds a current `type == page` target by its exact ID from `/json/list`, then permits only fixed `Runtime.evaluate` snapshot reads (URL, title, body text, HTML). Exposes no navigation, input, upload, or desktop-control operations. |
| `browser_actions.py` | Deterministic browser-action contracts for text replacement, native-option selection, radio/checkbox state changes, CDP file attachment, scroll-and-click, and one-shot submit/confirmation. Each requires exact post-action read-back evidence before an action is considered verified. |
| `cdp_page_executor.py` | Bounded exact-target action executor. Requires a fresh trusted read-only snapshot whose target ID and URL exactly match the request before delegating text replacement or real native-option selection; stale or untrusted state blocks before mutation. |
| `mutable_cdp_page_adapter.py` | Mutable exact-target CDP field adapter for sanitized/local preparation. Supports only visible, enabled text, native-select, checked-control, and file-input operations with fresh URL checks and post-operation read-back seams. Exposes no navigation, desktop input, coordinates, or hidden-control mutation. |
| `visual_escalation.py` | Universal bounded visual recovery contract shared by live ATS executors: one verified DOM/AX attempt, then one exact-page scoped screenshot/OCR inspection and one inspected retry, returning a stable blocker rather than raw desktop input or repeated retries. |
| `page_recovery.py` | Sanitized page-action journal for click/upload/save/submit recovery. Resumes only from verified state and turns an uncertain submit into a confirmation-inspection blocker rather than replaying it. |
| `retry_recovery.py` | Bounded recovery policy primitive: one normal attempt, then one inspection after a recoverable interruption. An inspector-confirmed completion is returned without replaying a potentially submitted action; a non-confirming inspection returns a stable blocker. |
| `session_gate.py` | Validates a tenant's runtime-only session reference and returns either authenticated-session reuse or an explicit human login/identity-verification gate. Never receives or serializes credentials. |
| `credential_adapter.py` | Secret-free runtime Keychain-reference contract. Checks only an approved item's service/account metadata through `security find-generic-password` without `-w`; returned plans contain availability metadata and a `runtime_only` reference, never a password. |
| `browser_integration_canary.py` | Sanitised non-mutating canaries for Njoyn, Workday, Greenhouse, Lever, and Oracle that fail closed on invalid Retina scale, stale target focus, hidden controls, overlays, or unexpected native windows while requiring submission to remain disabled. |

### Browser/CDP health check

```bash
python browser_health.py --base-url http://127.0.0.1:9222
```

Exit `0` means the endpoint is ready for automation. Exit `1` means the issue is recoverable and the JSON payload includes a stable `error_code` such as `connection_refused` or `no_page_targets`.

---

## Stage 2b — ATS platform handlers

Each handler encodes one platform's real behavior. All are non-submitting inspectors.

| Module | Responsibility |
|---|---|
| `greenhouse_handler.py` | Fixture-driven Greenhouse inspector with field inventory, resume read-back, manual-gate plumbing, and confirmation validation. |
| `greenhouse_guest_confirmation.py` | Guest-flow confirmation validation for Greenhouse. |
| `workday_handler.py` | Executable Workday listing/application inspector with wizard inventory, resume read-back, parsed-resume mismatch detection, save-draft awareness, multi-gate fail-closed output, and confirmation-reference extraction. |
| `lever_handler.py` | Fixture-driven Lever inspector with field inventory, upload read-back verification, manual-gate detection, confirmation validation, and a machine-readable CLI. |
| `oracle_handler.py` | Oracle Recruiting inspector with combobox validation, issue navigation, resume read-back, and confirmation validation. |
| `njoyn_handler.py` | Non-mutating CGI/Njoyn surface inspector (details below). |
| `schonfeld_form.py` | Client-bound custom guest form handler. |
| `ats_registry.py` / `prepare_job.py` | Shared non-submitting dispatcher for Greenhouse, Workday, Lever, Oracle, and CGI/Njoyn saved surfaces. Every payload explicitly carries `submission_enabled: false`; manual-gated and listing surfaces remain fail-closed. |
| `standard_ats_live_executor.py` | Shared non-submitting executor for Workday, Greenhouse, Lever, and Oracle. Validates the handler plan, batches approved known-page answers via exact read-back evidence, and always stops before submit for human Review. |
| `njoyn_live_executor.py` | Non-submitting CGI/Njoyn execution contract: batches an approved known-page answer map, verifies handler-plan parser-repair fields through exact read-back, and always returns `stop_before_submit`. |
| `answer_map_executor.py` | Bounded known-page answer-map executor: fills a complete approved map once and returns field-by-field post-fill read-back evidence. A batch is verified only when every field exactly matches. |
| `tenant_field_maps.py` | Versioned exact-host/path learned controls and conditional steps for sanitized Greenhouse, Workday, Lever, Oracle, and Njoyn tenants. Semantic keys map to one allowlisted operation/selector; raw selectors, unknown tenants/steps, missing observed controls, unsupported combobox mutation, credential fields, and unmet parser/question/Review conditions fail closed. |
| `tenant_metadata.py` | Loads versioned learned-tenant records only after matching page hostname, ATS platform, and tenant identity; returns a secret-free runtime-only session reference or fails closed. |
| `ats_preflight.py` | Pre-interaction surface checks before any field action. |
| `question_engine.py` / `canonical_answers.py` / `answer_coverage.py` | Resolve semantic answers, verify coverage of every required field, and refuse unknown questions. |

`prepare_job.py --tenant-metadata <path>` loads a matching learned tenant record only after hostname/platform validation. It carries only a runtime-only session reference and authenticated-state metadata into the plan, allowing a repeat flow to reuse an already authenticated session without serializing credentials or scheduling account creation.

### Njoyn handler detail

`njoyn_handler.py` inventories listing identity/Apply entrypoints, account email/password controls, privacy-notice acknowledgement controls, employment-disclosure radios, voluntary-disability selects, resume-upload controls with attached-filename read-back verification, explicit parsed-profile mismatch markers, referral parent/child selects, questionnaire controls, and verified confirmation evidence with an exact CGI reference identifier when rendered.

It reports parser correction requirements without silently accepting parsed data, verifies that referral source state is a real `Social Media` → `Instagram` selection rather than typed text, and treats account sign-in/profile creation, privacy notices, required employment disclosures, voluntary disability disclosures, parser corrections, incomplete referral selections, and unresolved required questionnaires as fail-closed manual gates until explicitly handled.

---

## Stage 3 — Preparation and authoritative Review

### Guarded live preparation

Keep the approved-answer map and generated evidence under ignored `runtime/`. After independently reading the current page target ID and exact identity:

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

`prepare_live_job.py` is a guarded exact-target, non-submitting live-preparation CLI and seam. The production CLI accepts only a loopback CDP origin, freshly binds the requested page target, requires exact URL/company/role/requisition/platform/learned-step evidence, dispatches the ATS handler, runs answer coverage, and resolves explicit semantic answers through a versioned tenant map. Every field must pass post-action read-back before the command persists a Review-ready bundle; persisted evidence retains semantic field/selector verification but strips profile and answer values.

The approved-answer file uses semantic learned keys such as `first_name`, never CSS selectors. The command never navigates or submits. A changed target/URL, unsupported or gated ATS surface, unknown tenant/step/key, identity or handler-platform mismatch, unmet conditional step, or failed field read-back exits nonzero without writing Review evidence.

### Authoritative Review

`review_reconciler.py` is a pure authoritative-Review reconciler. It compares both prepared and server-rendered target identity, every supplied profile field, the exact `Resume.pdf` basename/content hash, required parser repairs, and required-question read-back. Any difference is retained as a sanitized `human_required` blocker; an all-exact artifact receives a canonical SHA-256 for later approval binding but explicitly carries `submission_authorized: false`.

`reconcile_review(...)` must receive a fresh server-rendered Review inventory, independently derived profile/resume facts, required parser-repair fields, required-question IDs, and the exact expected target. Only `review_authoritative: true` with an empty `human_required` list can be presented for approval — and it is never itself permission to submit.

---

## Stage 4–5 — Authorization and one-shot submit

| Module | Responsibility |
|---|---|
| `submission_authorization.py` | Local SQLite store for expiring, single-use submission authorization. Issuance recomputes and verifies an authoritative Review artifact hash, binds job ID/target ID/URL/requisition/hash/actor, and stores only a SHA-256 token digest. Consumption is atomic; replay and expiry fail closed, and any target or Review drift permanently invalidates the authorization. |
| `one_shot_submit.py` | Irreversible one-shot submit coordinator over a deliberately narrow exact-page protocol. Blocks mandatory human gates and unapproved MAANGO before token consumption, verifies one visible/enabled/unique submit button, consumes exact-bound authorization, journals intent before one scoped click, and thereafter permits confirmation inspection only. |
| `submission_ledger.py` | Durable record of submission attempts and outcomes. |
| `execution_journal.py` | Append-only journal of executed stages for recovery. |
| `legacy_submission_migration.py` | Reconcile historical submission records into the current ledger schema. |

Keep the returned opaque token runtime-only. It is actor-bound, expires at the stated instant, can be consumed once, and is permanently invalidated if the current job ID, target ID, URL, requisition, or Review hash differs.

`execute_one_shot_submit(...)` is the only submit coordinator. It requires the exact page seam to re-read target and submit-control evidence immediately before the one click. A CAPTCHA, assessment, email/identity gate, unapproved MAANGO job, target/control drift, interruption, or missing confirmation stops the flow. Once authorization is consumed, recovery is confirmation inspection **without replay** — interruption can never route back to a second click.

---

## Stage 6–7 — Confirmation and delivery

| Module | Responsibility |
|---|---|
| `confirmation_reconciliation.py` | Two-source learned-ATS submission proof for Greenhouse, Workday, Lever, Oracle, and Njoyn. |
| `live_confirmation_reader.py` | Reads rendered confirmation surfaces for the learned platforms. |
| `live_review_reader.py` | Reads server-rendered Review surfaces. |
| `post_submit_transaction.py` | Durable per-job portal → tracker/read-back → Discord/read-back coordinator with no submit API. |
| `live_delivery_adapters.py` | Google Sheets and Discord transaction adapters requiring the `commit_external` capability. |
| `tracker.py` | Read the live Google Sheet, append rows with mandatory API read-back verification, and run a self-cleaning integration check. |
| `notifier.py` | Send deterministic Discord alerts. |
| `discord_controls.py` | Enforce job-ID-bound approve/reject/retry/skip actions against the local SQLite queue. |
| `submission_artifacts.py` | Build sanitized submission-evidence artifacts reconciling verified tracker rows with Discord applied notifications. |
| `audit_log.py` | Append structured JSONL audit events with recursive sensitive-field redaction. |
| `timing_telemetry.py` | Emit PII-free elapsed-second evidence for discovery, login, upload, form fill, parser repair, Review, confirmation, tracker read-back, and Discord read-back. |

### Two-source confirmation

A platform handler must first classify sanitized HTML as confirmation. Then candidate-home/application-list evidence must contain **exactly one** matching platform/company/role/requisition record with both `state: submitted` and `submitted: true`. Requisition, identity, state, and ambiguity drift remain explicit blockers; raw HTML is replaced by a SHA-256.

After any observed confirmation, `extract_confirmation(...)` must verify it through the matching learned ATS handler and `reconcile_candidate_portal(...)` must independently read back one exact submitted application record. Only `portal_confirmed: true` and `safe_for_post_submit: true` may enter the tracker/notification transaction. **A success-looking page alone is insufficient.**

### Delivery transaction

`PostSubmitTransactionCoordinator` enforces tracker append plus exact read-back before Discord send plus exact read-back. It atomically records an attempt claim before either downstream side effect, hashes rather than persists tracker/message payloads, and completes only after exact Discord read-back. Partial failures resume by read-back only, preventing duplicate tracker rows or messages. A changed payload or portal artifact is rejected instead of spawning a duplicate transaction.

### Queue-bound Discord controls

```bash
python discord_controls.py job:42:approve --queue-db runtime/production-run/app_queue.sqlite3
```

Accepts only job-ID-bound control IDs (`job:<id>:<action>`) and fails if the referenced queue job is missing or in the wrong state. Supported actions:

- `approve` / `reject` for `pending_approval` jobs
- `retry` / `skip` for `pending_question` and `pending_captcha` jobs

On success it emits machine-readable JSON describing the applied action, resolved status (`approved`, `rejected`, `retried`, `skipped`), and updated queue record. The Discord integration may bind commands to durable, actor-specific single-use control tokens; a token is valid only for its exact control and actor before expiry. Replay/expired-token denials leave the queue unchanged and are audit logged without recording the token.

---

## The unified live CLI

`live_run_manifest.py` defines the closed v1 runtime contract. It binds one mode, job/queue ID, exact target ID/URL, company, role, requisition, learned platform/tenant, verified profile and exact `Resume.pdf` hashes, explicit manual-gate state, and unique absolute runtime artifact paths. Unknown or missing fields and observed identity drift fail closed. A `production_live` manifest is inert unless the caller separately passes explicit production enablement — setting the mode inside the manifest cannot enable itself.

`production_operator.py` is the one approval-gated operator CLI. `local-demo` retains the marker-checked fixture proof; the `live` family adds manifest-bound preflight, preparation, authoritative Review, protected authorization, one-shot submit, learned confirmation, commit-gated delivery, read-only recovery, and a non-authorizing release audit. Production paths require separate caller enablement at every stage.

### 1. Prepare

```bash
python production_operator.py live prepare \
  --manifest runtime/live-run/manifest.json \
  --approved-answers runtime/live-run/approved-answers.json \
  --step application \
  --cdp-base-url http://127.0.0.1:9222
```

Never chooses a tab — the exact target ID comes from the manifest. Before any mapped field action it verifies loopback CDP health, current target/URL and job identity, learned tenant and step, answer coverage, visible/unobscured controls, and profile-selected `Resume.pdf` bytes. The result contains identifiers, verified field evidence, and gate booleans only. Production manifests additionally require `--enable-production-live`.

### 2. Review

```bash
python production_operator.py live review \
  --manifest runtime/live-run/manifest.json \
  --approved-answers runtime/live-run/approved-answers.json \
  --step application \
  --required-question work_authorization
```

Freshly rebinds and revalidates the exact page, reads only a learned platform Review seam (falling back to conservative versioned-map observation), and compares it with the prior preparation, explicit approved answers, and exact resume evidence. Stdout contains only the Review hash, verified field identifiers, blockers, and exact job identity. Missing server resume hashes, parser repairs, required-question evidence, or tenant readers remain blockers.

### 3. Authorize

```bash
python production_operator.py live authorize \
  --manifest runtime/live-run/manifest.json \
  --actor '<explicit-operator-identity>' \
  --approve-review-hash '<exact-review-sha256>' \
  --expires-in-seconds 300
```

Expiry is explicit and capped at 600 seconds. MAANGO runs require both `manual_gate.maango_approved: true` in the manifest and `--approve-maango`. The opaque single-use token is never printed: it is written once with mode `0600` to `runtime_paths.authorization_handoff`; the database stores only its digest. An existing handoff, Review/job drift, any blocker, mismatched hash, or uncleared manual gate stops issuance.

### 4. Submit

```bash
python production_operator.py live submit \
  --manifest runtime/live-run/manifest.json \
  --approved-answers runtime/live-run/approved-answers.json \
  --step application \
  --required-question work_authorization \
  --actor '<same-operator-identity>'
```

Immediately before consumption and again before the sole DOM activation, verifies loopback health, exact target/URL/job/tenant identity, page gates and MAANGO state, the visible/enabled/unique learned submit button, and a newly reconciled Review hash equal to the approved hash. Submit intent is written to `runtime_paths.submit_journal` before the click. Once consumed, the raw-token handoff is removed; interruption or missing confirmation always returns `inspect_confirmation_without_replay`. This command has no tracker or notification path.

### 5. Confirmation

```bash
python production_operator.py live confirmation --manifest runtime/live-run/manifest.json
```

Requires exact submit-journal evidence, rebinds only the manifest target, validates confirmation through the matching learned ATS handler, and calls the verified `(platform, tenant)` Candidate Home reader. Njoyn, Workday, Greenhouse, Lever, and Oracle are registered. Exactly one matching company/role/requisition record must report both `state: submitted` and `submitted: true`. An unavailable tenant reader, uncertain confirmation, identity/state mismatch, or duplicate match becomes `human_required`.

### 6. Deliver

```bash
python production_operator.py live deliver \
  --manifest runtime/live-run/manifest.json \
  --submitted-date 2026-08-27
```

Requires the exact portal-confirmed artifact. The durable coordinator performs tracker lookup/append/authenticated read-back before Discord lookup/send/authenticated read-back, with one stable transaction ID and separate payload/message hashes. Sanitized mode forbids `--commit-external` and uses local adapters. A `production_live` manifest additionally requires `--enable-production-live --commit-external --discord-channel-id '<exact-channel-id>'`; the Discord token is fetched at call time from the named environment variable and is never persisted.

### Status and recovery

```bash
python production_operator.py live status --manifest runtime/live-run/manifest.json
python production_operator.py live resume --manifest runtime/live-run/manifest.json
```

`status` writes the value-free seven-stage report and recommends exactly one next action. `resume` can perform only confirmation inspection after submit intent, or durable tracker/Discord read-back after a claimed downstream attempt. It never calls prepare, Review, authorization, or submit. An uncertain or already verified submit always has `submit_replay_allowed: false`; missing authorization handoffs and invalid artifacts route to human review instead of token reissuance.

---

## Unattended controller

| Module | Responsibility |
|---|---|
| `autonomous_controller.py` | Policy-scoped unattended run controller. |
| `autonomous_backend.py` | Backend execution for controller-scheduled runs. |
| `queue_worker.py` | Lease-based worker that resumes or prepares queued jobs. |
| `worker_operator.py` | Client-bound Review, single-use submit, and guest evidence. See [WORKER-OPERATOR.md](WORKER-OPERATOR.md). |
| `production_run.py` | Production run entrypoint. |
| `operational_health.py` | Aggregate health signals for a running deployment. |
| `queue_sheet_reconciliation.py` | Reconcile queue state against the tracker sheet. |
| `kevin_bible_sync.py` | Sync the clarification document used for unclear profile answers. |

`autonomous_config.example.json` intentionally has `production_enabled: false`; copying it does not authorize or start applications. See [AUTONOMOUS-OPERATION.md](AUTONOMOUS-OPERATION.md).

---

## Testing and audits

| Module | Responsibility |
|---|---|
| `run_offline_tests.py` | Offline test runner with an audit hook that forbids real network/browser connections and external application launches. |
| `fixture_e2e.py` | Non-submitting vertical fixture flows for supported ATSs. |
| `local_cdp_operator.py` | Real local Chrome-for-Testing integration harness against sanitized fixtures. |
| `production_readiness.py` | Read-only final audit of persisted dry-run, canary, and fixture evidence. |
| `setup_diagnostics.py` | Offline readiness checks for profile, resume, Google Sheets OAuth, and optional browser/CDP access. |
| `resume_preflight.py` | Verify the exact resume file selected by the profile. |
| `tests/` | 1274 behavior and safety tests. |
| `fixtures/` | Harmless Greenhouse, Workday, Lever, Oracle, and CGI/Njoyn test pages. |

### Run the tests

```bash
python run_offline_tests.py
```

Requires Python 3.11+ — see the Python version note below.

### Sanitized real-Chrome integration proof

```bash
python -m pytest tests/test_local_cdp_operator.py -q
```

Launches an installed local Chrome-for-Testing binary with an ephemeral profile and CDP pipe transport, opens only the repository's marker-checked static fixture, and runs the complete guarded preparation → Review → authorization → one-shot submit → confirmation → local tracker/Discord-read-back flow. It deliberately simulates a post-click interruption and then reattaches the exact target; **the submit counter must remain one.** It also proves overlay blocking, Retina scaling, observation-only scoped screenshot escalation, and stale-URL rejection.

### Production operator proof

```bash
python production_operator.py local-demo \
  --resume runtime/sanitized-demo/Resume.pdf \
  --runtime-dir runtime/operator-demo \
  --output runtime/operator-demo/report.json \
  --approve-sanitized-submit
python production_operator.py audit --report runtime/operator-demo/report.json
```

The approval flag applies only to the marker-checked static fixture. Before its local submit, the command requires exact Chrome/CDP target health, a passing Retina canary, no mandatory gate or MAANGO routing, exact `Resume.pdf` preflight, all seven learned-map read-backs, and authoritative Review. The report contains no answer values, authorization token, local path, HTML, tracker payload, or Discord message. Preparation must remain below 300 seconds and verified local submission below 600 seconds. A successful audit returns `ready_for_manual_live_authorization_review` while keeping `real_application_authorized: false`.

### Production-readiness audit

```bash
python production_readiness.py \
  --dry-run-report runtime/production-run/report.json \
  --fixture-flows runtime/fixture-flows.json \
  --learned-ats-benchmark runtime/njoyn-benchmark.json
```

Read-only. Returns `ready_for_human_gated_production` only when persisted evidence proves idempotent, non-submitting dry-run behavior and all supported ATS fixture flows remained non-submitting. With `--learned-ats-benchmark` it additionally requires CGI/Njoyn preparation below 300 seconds and fully verified submission below 600 seconds. It explicitly preserves human-only gates: CAPTCHA, email/identity verification, assessments, unknown required questions, and explicit submission authorization.

### Release audit

```bash
python production_operator.py live release-audit --evidence runtime/live-release-audit.json
```

A passing audit reports `ready_for_manual_live_authorization_review` while keeping `real_live_enabled`, `commit_external_enabled`, and `real_application_authorized` false. It verifies recorded TDD/full-suite results, ordered task commits, sanitized real-Chrome submit-count/replay evidence, read-only normal-Chrome preflight, documentation, source safety, and worktree hygiene. It is release evidence only; it cannot replace any per-command production, Review, actor, MAANGO, single-use authorization, external-commit, or authenticated read-back gate.

### Other smoke tests

```bash
python setup_diagnostics.py --skip-browser
python tracker.py integration-check --tag local-smoke
python production_operator.py live preflight \
  --manifest runtime/live-run/manifest.json \
  --cdp-base-url http://127.0.0.1:9222
```

`setup_diagnostics.py` validates the local `profile.json`, confirms `resume.primary` points to a real file, and checks the Google Sheets write token. `tracker.py integration-check` snapshots current rows, appends one clearly-marked test row, verifies via fresh read-back, then restores the original rows. `live preflight` binds only the manifest target through the read-only transport, takes two fresh snapshots, verifies unchanged content and exact learned identity, and exposes no mutation or submit operation.

---

## Python version requirement

**Python 3.11 or newer is required.** `submission_ledger.py` imports `from datetime import UTC, datetime, timedelta`, and `datetime.UTC` was added in 3.11. macOS system Python (`/usr/bin/python3`) is 3.9 and fails at import time:

```
ImportError: cannot import name 'UTC' from 'datetime'
  submission_ledger.py -> one_shot_submit.py -> production_operator.py
```

Because `production_operator.py` imports that chain at module load, **every** `live` subcommand dies before argument parsing — including `--help`. The traceback names `datetime`, so it reads like a stdlib problem rather than an interpreter mismatch.

Do not "fix" this by rewriting the import or pinning to system Python. Discover an available interpreter:

```bash
for p in python3.13 python3.12 python3.11 /opt/homebrew/bin/python3 /opt/anaconda3/bin/python3; do
  v=$(command -v $p 2>/dev/null) || continue
  echo "$v -> $($v --version 2>&1)"
done
```

Use the same interpreter for the offline test runner and the live CLI so import behavior matches. Note that a bare `python3` in a piped command can resolve to the 3.9 system binary even when a newer one is earlier in an interactive `PATH` — prefer the absolute path in automation.

---

## Privacy design

Personal profiles, resumes, OAuth credentials, tracker snapshots, and generated runtime artifacts are excluded from version control via `.gitignore`.

Beyond exclusion, evidence artifacts are **value-free by construction**. Persisted verification records retain semantic field and selector identifiers plus pass/fail state, but strip the actual answer values. Page HTML and tracker/message payloads are replaced by SHA-256 hashes. Authorization stores only a token digest, never the token. Credentials are referenced by Keychain service/account metadata and never read into the process.
