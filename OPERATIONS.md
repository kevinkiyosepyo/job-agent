# Operations Runbook

## Purpose

This repository is a local, safety-first job-agent build. The default mode is offline verification and dry-run orchestration only.

## Standard operator workflow

1. Run the full test suite.
2. Run offline setup diagnostics.
3. Optionally probe browser/CDP health if browser automation is needed.
4. Use dry-run orchestration only unless a separate, explicit application flow is being exercised.
5. Verify tracker integration with the self-cleaning smoke test before any tracker-facing change ships.
6. Run the sanitized real-Chrome operator proof and independently re-audit its persisted report.

## Commands

### Full test suite

```bash
python -m pytest tests -q
```

### Offline readiness

```bash
python setup_diagnostics.py --skip-browser
```

### Browser/CDP readiness

```bash
python browser_health.py --base-url http://127.0.0.1:9222
```

Only bind a known exact page target. Mutable CDP preparation uses the local `MutableCDPPageAdapter` contract: each field operation re-reads the target URL, rejects absent/hidden/disabled controls, and is limited to text, native select, checked control, or file attachment. It must never navigate, use raw desktop input or coordinates, or operate on a changed target. Start live preparation only through the exact-target `prepare_live_job` seam; it is non-submitting, uses only explicitly approved answers, requires verified post-fill evidence, and fails before handler dispatch if target URL or company/role/requisition differs from the operator-bound request.

### Guarded non-submitting preparation

Store the explicit semantic answer map and output only under ignored `runtime/`; never put raw selectors in the answer file. Read the current target ID from the local CDP target list, independently verify the exact URL/company/role/requisition, and invoke `prepare_live_job.py` with `--target-id`, `--expected-url`, `--company`, `--role`, `--requisition`, `--platform`, `--step`, `--profile`, `--approved-answers`, and `--output`. The CDP origin must remain an uncredentialed loopback HTTP origin. Treat a nonzero exit as a hard stop: do not reuse an old target ID, manually edit failed evidence into a passing state, or proceed when any field lacks verified read-back. The successful artifact intentionally omits answer/profile values and is only input to authoritative Review; it is not submission authority.

### Authoritative Review reconciliation

Re-read the server-rendered Review surface on the same exact target and reconcile it with `review_reconciler.py`. Review authority requires exact target ID, URL, company, role, and requisition; exact equality for all supplied profile facts; an independently preflighted file and server evidence both naming `Resume.pdf` with the same SHA-256; verified server read-back for every required parser repair; and answered plus verified evidence for every required question. Any `human_required` entry is a hard stop. The canonical Review hash binds the next approval step but does not authorize submission, and the artifact must never be edited to remove a blocker.

### Expiring single-use authorization

Issue authorization through `SubmissionAuthorizationStore` only for the unchanged authoritative Review artifact and an explicit operator actor. Set a short, explicit expiry and keep the returned token only in ignored runtime state; SQLite stores its digest, never the token. Immediately before submission, supply fresh job ID, target ID, URL, requisition, Review hash, and actor evidence to atomic consumption. Expired or replayed tokens are hard stops. Any binding drift permanently invalidates the token and requires a fresh Review plus fresh approval; returning the page to an earlier state does not restore it.

### One-shot submit and recovery

Use only `execute_one_shot_submit(...)` with an exact-target page implementation. Before authorization consumption it must observe no CAPTCHA, assessment, email-verification, or identity-verification gate; MAANGO requires separate explicit approval. The submit control must read back as one exact visible, enabled, unique button. After authorization consumption, verify the target/control again, append sanitized submit intent to the page journal, and call the one-shot submit method once. A successful click is not proof of submission: inspect confirmation. If the call is interrupted or confirmation is absent, never click again or issue a replacement token; follow `inspect_confirmation_without_replay` until Task 6 reconciliation proves the outcome.

### Confirmation and candidate-portal reconciliation

Run sanitized confirmation HTML through `extract_confirmation(...)` for the exact learned ATS platform. Then independently inventory candidate home/application list and call `reconcile_candidate_portal(...)`. The confirmation URL or reference must bind the requisition, and exactly one portal record must match platform, company, role, and requisition while explicitly reporting both `state: submitted` and `submitted: true`. Missing, pending, identity-mismatched, or duplicate records remain human-required. Preserve the sanitized text hash/reference only; do not persist raw confirmation HTML. Tracker or notification work is forbidden until both `portal_confirmed` and `safe_for_post_submit` are true.

### Post-submit delivery transaction

Pass only verified portal evidence to `PostSubmitTransactionCoordinator`. The coordinator first checks for an existing tracker row by transaction ID, records tracker-append intent before one append, and requires exact Sheets read-back of the transaction/payload hash. Discord is forbidden until that read-back is verified. It then checks for an existing message, records send intent before one send, and requires exact Discord read-back of the transaction/message hash. A partial result is resumable only through read-back; never manually retry append/send, alter hashed inputs, or revisit submit. The complete artifact contains hashes, receipt IDs, job identity, and verification flags only.

### Learned tenant maps and conditional steps

Resolve controls only through `tenant_field_maps.py`. The page URL and requested platform must select exactly one versioned hostname/path-bound tenant; unknown tenants require an explicit reviewed map change, never live selector discovery. Supply semantic answer keys for the current learned step. Validate observed selectors when inventory evidence is available, and stop on any control drift. Advance with `plan_next_step(...)` only when every required semantic field and condition is verified. Parser repair, required-question, authenticated-session, referral-option, Oracle combobox, and authoritative-Review conditions are hard gates. Human-required and submit controls are never executable as ordinary answer actions.

### Sanitized local Chrome integration

Run `python -m pytest tests/test_local_cdp_operator.py -q` before operator CLI changes. The harness is test-only: it accepts only the marker-checked repository fixture, an ephemeral profile, and an installed local Chrome-for-Testing executable. CDP travels through process-local pipe descriptors because no debugging port or browser-wide desktop control is needed. The proof must preserve one freshly discovered exact target ID/URL across preparation and submission, reject an overlay before mutation, verify every field by read-back, keep OCR observation scoped to a screenshot of that target, and retain a submit count of one across interruption and reattachment. Its tracker and Discord implementations are in-memory local fakes; substituting production adapters is forbidden in this test.

### Production operator proof and timing audit

Place a harmless exact `Resume.pdf` under ignored `runtime/`, then run `python production_operator.py local-demo --resume runtime/sanitized-demo/Resume.pdf --runtime-dir runtime/operator-demo --output runtime/operator-demo/report.json --approve-sanitized-submit`. The approval is deliberately named and scoped to the sanitized fixture; omitting it must stop before Chrome starts. The command has no live mode and cannot select a different fixture. It requires every operational health check before the fixture submit, uses the complete versioned Greenhouse field map, and records only the closed PII-free timing vocabulary. Preparation must be under five minutes and verified fixture submission under ten minutes.

Run `python production_operator.py audit --report runtime/operator-demo/report.json` as a separate read-only step. It recomputes health, timing, Review, single-use/replay, one-shot count, portal, tracker-read-back, Discord-read-back, and safety verdicts from the value-free report. Only `ready_for_manual_live_authorization_review` is a passing proof, and even that artifact explicitly retains `real_application_authorized: false`. Do not treat it as a submission token or connect the local tracker/Discord fakes to production services.

### Unified live-run manifest contract

Keep every unified-run manifest and all paths it names under ignored, access-controlled runtime storage. Validate it through `live_run_manifest.load_manifest(...)` before opening any stage. The v1 schema is closed and binds the exact target/job identity, independently verified profile and exact `Resume.pdf` digests, manual gates/MAANGO state, and a distinct path for each stage artifact. Never accept an edited manifest as production enablement: `production_live` additionally requires a separate caller-side enablement input, and a fresh observed binding must exactly equal the manifest before use.

For a sanitized/local manifest, run `python production_operator.py live prepare --manifest runtime/live-run/manifest.json --approved-answers runtime/live-run/approved-answers.json --step application --cdp-base-url http://127.0.0.1:9222`. Supply the exact target in the manifest; the command has no target auto-selection or navigation path. It must stop if CDP is not healthy, the exact target/identity changes, the handler or learned tenant differs, coverage remains human-required, controls are hidden/obscured, or the profile-selected PDF differs from the manifest. Treat the sanitized preparation artifact as input to Review only, never as approval or submission evidence.

Once the human has inspected the Review page, run `python production_operator.py live review --manifest runtime/live-run/manifest.json --approved-answers runtime/live-run/approved-answers.json --step application`, adding repeatable `--required-parser-repair` and `--required-question` identifiers from the learned flow. This stage rebinds rather than trusting preparation-time state. A platform-specific learned reader may supply server-rendered evidence; otherwise the mapped fallback deliberately leaves unavailable resume hashes and question/repair evidence unverified. A blocked Review is useful evidence and exits nonzero. Never edit blockers out of `runtime_paths.review` or treat its canonical hash as authorization.

Authorize with `python production_operator.py live authorize --manifest runtime/live-run/manifest.json --actor '<operator>' --approve-review-hash '<exact-hash-from-review>' --expires-in-seconds 300`. Retyping the exact hash is the explicit approval input; expiry must be 1–600 seconds. For MAANGO, also require the reviewed manifest flag and pass `--approve-maango`. Confirm that the protected handoff is mode `0600`; do not print, copy into logs, or move its token into another file. If a handoff already exists, determine its stage through the recovery command once available rather than deleting it and issuing another authorization.

Run `python production_operator.py live submit --manifest runtime/live-run/manifest.json --approved-answers runtime/live-run/approved-answers.json --step application --actor '<same-operator>'`, repeating every required repair/question flag used for Review. The stage must recompute the same authoritative Review hash while holding the fresh exact-target binding. It then consumes once, journals intent, rechecks gates and the exact learned submit button, and performs one DOM activation. A consumed handoff is retired. Any post-consumption error is confirmation inspection only: never recreate the handoff, reauthorize, or call submit again. `confirmation_observed` is still not tracker-safe until learned confirmation and Candidate Home reconciliation pass.

### Tracker smoke test

```bash
python tracker.py integration-check --tag local-smoke
```

### Dry-run orchestration

```bash
python orchestrator.py verified-candidates.json --output orchestrator-report.json
```

## Incident triage

### Browser/CDP unavailable

1. Run `python browser_health.py --base-url http://127.0.0.1:9222`.
2. If the result is recoverable with `connection_refused` or `no_page_targets`, treat it as an environment issue rather than an application bug.
3. Re-check with `python setup_diagnostics.py` after the browser is back.

### Tracker/API concerns

1. Run `python tracker.py integration-check --tag local-smoke`.
2. Confirm the command restores original rows after read-back verification.
3. Do not modify production rows manually as a substitute for failed verification.

### Duplicate or overlapping runs

1. Treat `Another job-agent run is already active` as expected lock protection.
2. Verify the active process before removing any stale lock file.
3. Prefer waiting for the active run to complete over forcing a second run.

## Security review checklist

- Runtime artifacts must stay out of git (`runtime/`, `orchestrator-report.json`, logs, generated JSON plans).
- Personal profile data, resumes, OAuth tokens, and tracker snapshots must remain ignored.
- Dry-run commands must not submit applications, notify third parties, or mutate production trackers without explicit integration-check behavior.
- Confirmation evidence must be validated from actual confirmation text, not assumed from button clicks.
- New automation must preserve MAANGO manual-only routing and CAPTCHA stop conditions.
- `prepare_live_job.py` evidence must contain no answer/profile values, and its Review-ready result must never be treated as submit authorization.
- Authoritative Review artifacts must stay value-free, require exact `Resume.pdf`, and retain every target, parser, or required-question discrepancy as human-required.
- Authorization tokens must remain runtime-only, expire explicitly, be consumed once, and be reissued only after a fresh authoritative Review when any binding drifts.
- Submit intent must be journaled before the only exact click; interruption and unknown confirmation state are inspection-only and must never replay submission.
- A success-looking confirmation page is insufficient: learned-handler confirmation and an exact, unique, explicitly submitted candidate-portal read-back are both mandatory.
- Tracker append/read-back must precede Discord send/read-back; partial recovery is read-back-only and may never duplicate tracker, message, or submit side effects.
- Production preparation must use exact versioned tenant maps and semantic keys; unknown selectors, tenants, steps, or unmet transition conditions must never trigger live rediscovery.
- The real-Chrome integration must remain static-fixture-only, pipe-scoped, ephemeral, and sanitized; it must not bind production pages, production tracker/Discord adapters, or any desktop-input facility.
- The operator proof report must remain value-free and path-free, meet both timing targets, retain submit count one and replay denial, and explicitly state that no real application is authorized or submitted.

## Release checklist for engineering changes

1. Add or update tests first.
2. Watch the new test fail.
3. Implement the minimum fix.
4. Re-run the targeted test.
5. Run `python -m pytest tests -q`.
6. Review `git status --short` for unexpected sensitive or generated files.
7. Commit only verified code and documentation.
