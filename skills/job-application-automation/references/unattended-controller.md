# Guarded unattended controller

When configuring the repository controller, read `~/Documents/job-agent/autonomous_operation.md` and the actual CLI/source before enabling it. `autonomous_config.example.json` intentionally has `production_enabled: false`; copying it does not authorize or start applications.

The deterministic controller uses canonical facts, a generation-token queue, a shared account/tenant/requisition submission ledger, and the existing production operator. Unknown dispatched intents stop new submissions. Positive confirmation starts a rolling one-hour cooldown without catch-up. Notification retry is independent of submission and does not require Sheets.

The current backend's learned one-page scope is not a general ATS filler. Unsupported form families and unknown material eligibility or answer facts are parked, never silently treated as ineligible or guessed. A public job feed or a detected ATS is not proof of filling support.

Before live enablement, verify exact current normal-Chrome worker health; reconcile registered legacy journals plus known manual/ad-hoc application history; verify old writers are inactive; run the guarded offline suite and a separately authorized connected live validation for each enabled form family. Never use an empty new ledger to forget prior uncertainty. Never mark unknown historical attempts successful or release them just to unblock a run.

Use `run_offline_tests.py` for repository regression tests. Excluded isolated-Chrome tests are not live readiness evidence. Preserve concurrent dirty work with source snapshots, compare-and-swap merges, and a neutral resolution of overlapping changes. A release report must distinguish code installed, tests passed, service enabled, verified applications, and notification receipts.
