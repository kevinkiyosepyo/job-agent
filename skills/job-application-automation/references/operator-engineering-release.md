# Operator Engineering and Release Discipline

Use when extending `~/Documents/job-agent` or deciding whether the automation is actually complete.

## Unattended-operation boundary

The current repository is not an autonomous application service merely because the guarded live CLI exists:

- `production_run.py` is dry-run discovery/queueing only.
- `queue_worker.py` prepares caller-supplied saved HTML; it does not navigate a live job, authenticate, or drive the live submit stages.
- The live CLI requires a caller-supplied exact target and per-job Review/actor authorization.
- Most `live_confirmation_reader.VERIFIED_READERS` entries are fixture/example tenants, not production tenant contracts.
- `credential_adapter.py` checks Keychain metadata only; executable login/create/reset flows still need a separately tested runtime adapter.

Do not schedule unattended submissions until one durable runner composes discovery, exact-target navigation, authentication, preparation, Review, policy authorization, one-shot submit, confirmation, and notification with crash-safe state and rate limits.

## Known P0 live-safety blockers

Until the repository fixes and regression-tests all of these, automatic live submission must remain disabled:

- A fresh authorization can currently reach a second Submit click for the same job after an earlier uncertain submit intent; uniqueness is token-scoped rather than durable job/requisition-intent-scoped.
- The mapped Review fallback can treat mutated DOM presentation as authoritative without proving framework/server persistence, and required-question reconciliation uses unsafe selector-substring matching.
- Greenhouse text-only gate detection can miss rendered reCAPTCHA, hCaptcha, or Turnstile iframe/widget surfaces.
- Production confirmation/Candidate Home readers are unavailable for most real tenants and the strict original-URL binding does not yet model legitimate post-submit redirect/target lineage.
- Queue leasing lacks owner/fencing identity and an atomic conditional claim; queue `applied` state is not evidence-bound to Review, submit intent, and portal confirmation.
- Runtime profile, answer, manifest, Review, journal, and authorization artifacts must be private (`0700` directories, `0600` files), and audit logs must use an allowlist rather than retaining unrecognized personal fields.

## Definition of done

Do not equate any one of these with production completion:

- a handler contract exists;
- fixture tests pass;
- a local sanitized Submit succeeds;
- a release audit says `ready_for_manual_live_authorization_review`;
- an agent process exits with code 0.

A feature is complete only when the requested layer exists, its focused RED→GREEN evidence and full suite pass, the ordered commits are present in the native repository, the worktree is deliberate/clean, the skill/runbook routes future sessions to it, and the documented safety boundary is stated accurately. A non-authorizing local proof must never be described as real-live authorization.

## Urgent continuous build mode

When Kevin says `continue rn`, `one shot`, or says periodic cycles are too slow:

1. Stop or pause overlapping cron builders before another process edits the repository.
2. Verify a clean baseline or preserve unrelated changes explicitly.
3. Run one continuous coding-agent process with a high turn budget; do not replace it with three-minute cron slices.
4. Give the process the ordered queue, strict TDD contract, safety boundaries, final verification commands, and instruction not to stop after one commit.
5. Monitor actual Git/test state, not just the child agent's narrative.
6. If the process exits mid-queue, resume the exact session or start from the exact recorded next slice immediately.

## Release evidence freshness

`production_operator.py live release-audit` currently validates the supplied JSON schema and booleans; it does not independently rerun tests, inspect Git, or prove the evidence belongs to the current checkout. Never certify a release from an existing `runtime/live-release-audit.json`. First run the checks against the current worktree, regenerate the value-free evidence with the current test count and commit identity, and compare it to live `git status`/test output. If the JSON says clean/passing while the live checkout is dirty or failing, the live result wins and the release is not ready. A production hardening task should replace self-asserted evidence with an audit command that executes or cryptographically binds the checks to the current commit and toolchain.

## Child-agent claims are not evidence

After any autonomous run:

```bash
git status --short
git log --oneline -15
python -m pytest tests -q
git diff --check
```

Also inspect the relevant SPRINT section and scan executable source for prohibited desktop automation. An exit code or self-reported test count is not sufficient.

## Git sandbox handoff

A coding sandbox may write the worktree but not the native `.git`. When the agent has produced an ordered verified mirror/bundle:

1. List the bundle heads and verify its head descends from current `main`.
2. Fetch it into a temporary branch without changing the worktree.
3. Preserve the dirty worktree and unrelated untracked files in a named stash.
4. Fast-forward `main` to the temporary branch; never squash or recreate ordered task commits.
5. Run the full suite, whitespace check, forbidden-source scan, local release proof, and clean-worktree check in the native repository.
6. Keep the preservation stash until unrelated artifacts are accounted for; do not destructively discard user work.

## Release boundary

The unified CLI is stage-gated. A passing release audit intentionally reports:

- `real_live_enabled: false`
- `commit_external_enabled: false`
- `real_application_authorized: false`

Real operation requires a separately enabled production manifest and fresh stage-specific gates. Never infer authority from a skill, fixture, prior approval, or local audit.