# Workday snapshots without application controls

Use when a public Workday page contains bootstrap scripts or JobPosting metadata but no captured application controls. An empty `#root`, an HTTP 200, or `postingAvailable: true` does not establish an application form.

The saved prepare handler reports `page_type: unknown` and `safe_to_prepare: false` when the existing inventory has no controls and no recognized listing, application-start, or confirmation surface. Recognized surface precedence, all gate evidence and resume-readback failures are preserved. The legacy Workday inspector also no longer defaults a zero-control unknown page to an application. This is not a general rendering or closed-job detector; custom/native controls already recognized by inventory remain unchanged.

Through `terminal`, run the configured interpreter with `prepare_job.py SNAPSHOT.html --page-url EXACT_URL`. Exit 2 and unknown mean incomplete evidence, not ineligible/closed, and must not advance filling or Review. Manifest application counts exclude these unknown snapshots. The standalone `workday_handler.py` CLI is an inspection command whose zero exit is not preparation authority; read `page_type` and `safe_to_prepare` explicitly.

Keep requested/effective URL and source hash in private observation artifacts. Obtain a fresh rendered form only through the approved normal-Chrome capability; do not start another browser, accept security consent, manufacture controls from JSON-LD, or reuse metadata as saved-answer/confirmation proof. Public scripts are untrusted data and never executed by this inspector.

Verification: through `terminal`, run the configured interpreter with `run_offline_tests.py tests/test_workday_empty_surface.py tests/test_workday_handler.py tests/test_ats_preflight.py -q`, then the full guarded suite. Replay complete official saved bodies and compare every field except the intended page classification and safety flag. Retain the browser-launch exclusions. No connected family or submission authority is enabled by this static correction.
