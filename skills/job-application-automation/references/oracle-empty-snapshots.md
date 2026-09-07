# Oracle snapshots without inventoried controls

Use when a saved Oracle Candidate Experience response contains only a shell, job-unavailable page, metadata, or unrecognized controls. Public retrieval success is not a rendered application.

`oracle_handler.py` retains existing recognized listing and confirmation precedence, then classifies otherwise-default application snapshots with zero inventoried fields as `unknown`. Only these unknown results gain `safe_to_prepare: false`; recognized results retain their prior output shape rather than gaining a new positive preparation flag. `prepare_job.py` exits 2 for the unknown result. Standalone inspector completion still returns 0, so read its payload; that exit is not preparation authority.

Read role/location/issue/resume evidence separately and preserve it. Unknown is not a claim that the employer closed the role, that the page has no actual controls, or that Oracle is unsupported everywhere. The existing parser may omit unlabelled controls; this guard does not repair their labels or establish complete inventory. Explicit closed-job evidence belongs to the exact official target, not generic template text.

Through `terminal`, run the configured interpreter with `run_offline_tests.py tests/test_oracle_empty_surface.py tests/test_oracle_handler.py -q`, then the full guarded suite. Check saved public replay outputs separately from explicitly synthetic regressions. Retain the browser-launch exclusions.

The change does not alter existing confirmation detection, invent an ATS route for a custom hostname, fill a form, recover the approved browser, or authorize a submission. Preserve uncertain intent and require independently grounded canonical Review and explicit one-shot authorization for actual submissions.
