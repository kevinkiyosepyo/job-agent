# Unified Live Production CLI

Read this reference before any `production_operator.py live` command. Repository: `/Users/kevinpoopz/Documents/job-agent`. The commands bind one caller-supplied exact target and never grant permission merely because a manifest or local audit exists.

## Authority boundary

- Use `sanitized_local` for development and integration. It must not access a production ATS, credentials, the live tracker, or a real Discord channel.
- A `production_live` manifest is inert unless the current command also has `--enable-production-live`. Add that flag to each production command below; never carry authority forward implicitly.
- `live authorize` requires the exact authoritative Review hash, a named actor, a 1–600 second expiry, and `--approve-maango` when applicable. The raw token stays only in the mode-`0600` handoff and is single-use.
- `live submit` is the only submit path. It journals intent before one exact DOM activation. Any uncertainty after intent means confirmation inspection without replay.
- `--commit-external` is valid only for production delivery after exact portal confirmation. It does not authorize submission and must be paired with an exact Discord channel ID plus authenticated tracker and Discord read-back.
- `live release-audit` is read-only and never enables production, external commit, or a real application.

## Exact command order

Use the same reviewed manifest, approved-answer file, semantic step, required repairs/questions, and operator identity throughout. Replace placeholders deliberately; never auto-select a target or discover selectors live.

1. Confirm loopback CDP health and observe the exact normal-Chrome target without mutation:

   ```bash
   python browser_health.py --base-url http://127.0.0.1:9222
   python production_operator.py live preflight \
     --manifest runtime/live-run/manifest.json \
     --cdp-base-url http://127.0.0.1:9222
   ```

2. Prepare only the learned step and exact profile-selected `Resume.pdf`:

   ```bash
   python production_operator.py live prepare \
     --manifest runtime/live-run/manifest.json \
     --approved-answers runtime/live-run/approved-answers.json \
     --step application \
     --cdp-base-url http://127.0.0.1:9222
   ```

3. After the human visibly reaches Review, read and reconcile the authoritative server surface:

   ```bash
   python production_operator.py live review \
     --manifest runtime/live-run/manifest.json \
     --approved-answers runtime/live-run/approved-answers.json \
     --step application \
     --required-question work_authorization \
     --cdp-base-url http://127.0.0.1:9222
   ```

4. Independently inspect the value-free Review artifact, then issue short-lived single-use authority by retyping its exact hash:

   ```bash
   python production_operator.py live authorize \
     --manifest runtime/live-run/manifest.json \
     --actor '<operator-identity>' \
     --approve-review-hash '<exact-review-sha256>' \
     --expires-in-seconds 300
   ```

   Add `--approve-maango` only after the separate MAANGO decision is explicit and the manifest records it.

5. Submit once, repeating the Review inputs and actor so the command can recompute authority on a fresh exact-target binding:

   ```bash
   python production_operator.py live submit \
     --manifest runtime/live-run/manifest.json \
     --approved-answers runtime/live-run/approved-answers.json \
     --step application \
     --required-question work_authorization \
     --actor '<operator-identity>' \
     --cdp-base-url http://127.0.0.1:9222
   ```

6. Reconcile learned confirmation and one exact Candidate Home/application-list record, even if submit returned an uncertain result:

   ```bash
   python production_operator.py live confirmation \
     --manifest runtime/live-run/manifest.json \
     --cdp-base-url http://127.0.0.1:9222
   ```

7. Only after `safe_for_post_submit: true`, run the downstream transaction. Sanitized mode uses injected/local adapters and must omit all production flags:

   ```bash
   python production_operator.py live deliver \
     --manifest runtime/live-run/manifest.json \
     --submitted-date YYYY-MM-DD
   ```

   A separately approved production delivery additionally requires `--enable-production-live --commit-external --discord-channel-id '<exact-channel-id>'`. Provide only the environment-variable name through `--discord-token-env`; never put a token value in a command, manifest, log, or skill.

8. Inspect durable state before recovery:

   ```bash
   python production_operator.py live status \
     --manifest runtime/live-run/manifest.json
   python production_operator.py live resume \
     --manifest runtime/live-run/manifest.json
   ```

   After submit intent, `resume` may inspect confirmation only. After tracker/Discord intent, it may perform authenticated read-back only. It never prepares, authorizes, submits, appends, or sends a second time.

## Failure and rollback rules

- Before authorization: fix the source profile/answer or learned map, discard only untrusted generated artifacts, rerun preflight/prepare/Review, and obtain a fresh Review hash.
- With an unconsumed authorization: do not edit its database or handoff. Let it expire; any binding drift requires a fresh Review and new authorization.
- After submit intent: there is no submit rollback. Never delete the journal, recreate a handoff, reauthorize, or call submit again. Run `status`, then confirmation/resume observation only.
- After tracker or Discord intent: do not manually append or resend. Resume the original transaction using the same date and production gates so it performs read-back/idempotency reconciliation.
- On CAPTCHA, assessment, identity/email verification, passkey, unknown material fact, target/tenant drift, hidden/obscured control, ambiguous portal record, or failed authenticated read-back: preserve evidence and stop for the human.

## Health and release verification

Before an engineering release, run:

```bash
python -m pytest tests/test_production_operator_live_chrome.py -q
python -m pytest tests -q
git diff --check
```

Also run the repository's prohibited executable-source scan, verify ten ordered queue commits, and confirm a clean worktree. Record those results in an ignored, value-free release-evidence JSON and audit it:

```bash
python production_operator.py live release-audit \
  --evidence runtime/live-release-audit.json
```

The evidence must record all ten completed tasks, focused TDD, the complete passing suite, marker-checked sanitized Chrome with submit count one/replay denial, read-only exact-target normal-Chrome preflight, documentation/skill updates, clean diff/worktree, no prohibited executable source matches, and all external/credential/production safety flags false. A passing audit is readiness evidence only; it explicitly returns `real_live_enabled: false`, `commit_external_enabled: false`, and `real_application_authorized: false` and never supplies any runtime gate listed above.
