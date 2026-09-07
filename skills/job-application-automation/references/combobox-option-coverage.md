# Combobox coverage is not free-text coverage

Use when saved ATS inventory contains `type=combobox`, including collapsed modern Greenhouse React Select controls. Through `terminal`, inspect untouched saved HTML with `prepare_job.py`, then use `_questions_from_fields` and `build_coverage_matrix` with the canonical profile for a non-mutating diagnostic.

- Preparation retains the combobox type. A known canonical fact alone yields `combobox_options_unverified`, not a known selectable answer; optional questions may be skipped. Unknown facts retain their original reason.
- This narrow path has no supported combobox option/binding proof. API values, visible text, native-select/radio metadata, and claimed bound flags cannot satisfy it. Do not relabel a combobox as text or choose another referral/school to clear the blocker.
- Native select/radio exact-option checks and ordinary free-text coverage remain separate. Existing independently verified learned browser paths are not expanded by this change.
- Reacquire the actual control and rendered options through the approved browser capability. Select the truthful real option and verify its saved state using the routed ATS procedure. Never treat a static API option list as a rendered selection.
- A raw handler's `safe_to_prepare` flag is not complete answer coverage, Review, eligibility, upload or submit authority. Preserve unknown intent and all application gates.

Verification: run the configured interpreter through `run_offline_tests.py tests/test_combobox_option_coverage.py -q`, then the full guarded suite. Replay exact saved public bytes: raw inventory/gates must stay unchanged while unsupported known combobox entries become blockers. Browser-launch exclusions remain mandatory; synthetic read-only page seams are not connected-browser support.
