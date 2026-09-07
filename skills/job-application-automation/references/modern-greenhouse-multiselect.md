# Modern Greenhouse multiselect inspection

Use `terminal` with `prepare_job.py SAVED_HTML --page-url EXACT_OFFICIAL_URL --output PRIVATE_REPORT` to inspect saved public controls. No browser or employer action is performed.

- `control_hints.react_multiselects` is positive static evidence from a unique-ID combobox beneath the exact `select__value-container--is-multi` class token. IDs are raw identifiers, not CSS selectors; bracketed IDs need proper escaping or ID lookup when a separately approved live adapter is used.
- An empty/missing hint list does not prove single selection. An API multi-value type can represent a checkbox group instead of a chip control. Compare the exact current control, not only the question wording, ID suffix or API type.
- Hints retain labels/required markup but set `source=static_html`, `bound_values_verified=false`, `options_verified=false`. They do not infer available options, selection state, rendered validity or live capability. Hidden validation companions remain in the ordinary field inventory.
- Do not send a multiselect to a single-value helper that clears prior chips. Under a separately approved connected flow, reacquire the live control, select the exact truthful option(s), verify the entire selected set and saved Review. Never choose all options merely because the group is required.
- Public question schemas can guide option discovery but cannot substitute for rendered exact option binding or canonical answer facts. Preserve supplied GPA and degree facts, and never fabricate an alternate email, license status or referral option.

Verification through `terminal`: `run_offline_tests.py tests/test_greenhouse_multiselect_hints.py tests/test_greenhouse_handler.py -q`, then the full guarded suite. Compare the same saved official body before/after, retaining unchanged question IDs, checkbox definitions, gates and `submission_enabled=false`. This is inspection coverage, not an exercised connected multiselect adapter.
