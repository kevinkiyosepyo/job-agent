# Operator Engineering and Release Discipline

Use when extending `~/Documents/job-agent` or deciding whether the automation is actually complete.

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