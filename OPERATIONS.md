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

Only bind a known exact page target. Mutable CDP preparation uses the local `MutableCDPPageAdapter` contract: each field operation re-reads the target URL, rejects absent/hidden/disabled controls, and is limited to text, native select, checked control, or file attachment. It must never navigate, use raw desktop input or coordinates, or operate on a changed target. Start live preparation only through the exact-target `prepare_live_job` seam; it is non-submitting and fails before handler dispatch if target URL or company/role/requisition differs from the operator-bound request.

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

## Release checklist for engineering changes

1. Add or update tests first.
2. Watch the new test fail.
3. Implement the minimum fix.
4. Re-run the targeted test.
5. Run `python -m pytest tests -q`.
6. Review `git status --short` for unexpected sensitive or generated files.
7. Commit only verified code and documentation.
