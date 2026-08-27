# Operations Runbook

## Purpose

This repository is a local, safety-first job-agent build. The default mode is offline verification and dry-run orchestration only.

## Standard operator workflow

1. Run the full test suite.
2. Run offline setup diagnostics.
3. Optionally probe browser/CDP health if browser automation is needed.
4. Use dry-run orchestration only unless a separate, explicit application flow is being exercised.
5. Verify tracker integration with the self-cleaning smoke test before any tracker-facing change ships.

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

Store the explicit selector-to-string answer map and output only under ignored `runtime/`. Read the current target ID from the local CDP target list, independently verify the exact URL/company/role/requisition, and invoke `prepare_live_job.py` with `--target-id`, `--expected-url`, `--company`, `--role`, `--requisition`, `--profile`, `--approved-answers`, and `--output`. The CDP origin must remain an uncredentialed loopback HTTP origin. Treat a nonzero exit as a hard stop: do not reuse an old target ID, manually edit failed evidence into a passing state, or proceed when any field lacks verified read-back. The successful artifact intentionally omits answer/profile values and is only input to authoritative Review; it is not submission authority.

### Authoritative Review reconciliation

Re-read the server-rendered Review surface on the same exact target and reconcile it with `review_reconciler.py`. Review authority requires exact target ID, URL, company, role, and requisition; exact equality for all supplied profile facts; an independently preflighted file and server evidence both naming `Resume.pdf` with the same SHA-256; verified server read-back for every required parser repair; and answered plus verified evidence for every required question. Any `human_required` entry is a hard stop. The canonical Review hash binds the next approval step but does not authorize submission, and the artifact must never be edited to remove a blocker.

### Expiring single-use authorization

Issue authorization through `SubmissionAuthorizationStore` only for the unchanged authoritative Review artifact and an explicit operator actor. Set a short, explicit expiry and keep the returned token only in ignored runtime state; SQLite stores its digest, never the token. Immediately before submission, supply fresh job ID, target ID, URL, requisition, Review hash, and actor evidence to atomic consumption. Expired or replayed tokens are hard stops. Any binding drift permanently invalidates the token and requires a fresh Review plus fresh approval; returning the page to an earlier state does not restore it.

### One-shot submit and recovery

Use only `execute_one_shot_submit(...)` with an exact-target page implementation. Before authorization consumption it must observe no CAPTCHA, assessment, email-verification, or identity-verification gate; MAANGO requires separate explicit approval. The submit control must read back as one exact visible, enabled, unique button. After authorization consumption, verify the target/control again, append sanitized submit intent to the page journal, and call the one-shot submit method once. A successful click is not proof of submission: inspect confirmation. If the call is interrupted or confirmation is absent, never click again or issue a replacement token; follow `inspect_confirmation_without_replay` until Task 6 reconciliation proves the outcome.

### Confirmation and candidate-portal reconciliation

Run sanitized confirmation HTML through `extract_confirmation(...)` for the exact learned ATS platform. Then independently inventory candidate home/application list and call `reconcile_candidate_portal(...)`. The confirmation URL or reference must bind the requisition, and exactly one portal record must match platform, company, role, and requisition while explicitly reporting both `state: submitted` and `submitted: true`. Missing, pending, identity-mismatched, or duplicate records remain human-required. Preserve the sanitized text hash/reference only; do not persist raw confirmation HTML. Tracker or notification work is forbidden until both `portal_confirmed` and `safe_for_post_submit` are true.

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

## Release checklist for engineering changes

1. Add or update tests first.
2. Watch the new test fail.
3. Implement the minimum fix.
4. Re-run the targeted test.
5. Run `python -m pytest tests -q`.
6. Review `git status --short` for unexpected sensitive or generated files.
7. Commit only verified code and documentation.
