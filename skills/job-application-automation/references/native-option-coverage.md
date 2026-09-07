# Native option coverage is not saved-answer evidence

Use when a known profile fact is intended for a native select in a prepared ATS inventory. Read the canonical profile/resume under the umbrella; a familiar question label is insufficient if the form lacks the intended option.

The existing `prepare_live_job` question conversion attaches native select definitions only when one nonempty inventory name and the original field label map uniquely to one inspected control/group. The displayed question may fall back from its label to its name. No match, duplicate names or malformed group collections leave `native_select=null`; malformed internals of a matched group are rejected by coverage. Neither case becomes a free-text fallback. Legacy free-text question behavior is unchanged. Native select handlers without option definitions remain unsupported for this check, not employer-ineligible.

`answer_coverage.build_coverage_matrix` counts a native-select fact as known only if:
1. A static native group exists, with single-selection and not-disabled attribute flags.
2. Every option has a string label and explicit string value attribute plus a boolean disabled flag. Missing values stay unsupported; they are not guessed from text, including when another option could hide a duplicate runtime value.
3. Exactly one option label equals the canonical answer; its raw value is nonblank and unique, and its option/optgroup disabled flag is false.

Absent/ambiguous/malformed options are human-required when the question is required, or optional-skip when optional. Never invent a referral alternative, choose a placeholder, coerce a school alias or relax a profile fact to pass this check. Approved tenant-specific normalization and live binding still need their own independently grounded paths.

These are static option-availability checks, not actual selectedOptions, effective fieldset/CSS interactability, answer persistence, independent Review or live capability. Output coverage remains answer-value-free. A known fact entry does not prove it was filled; do not promote it to Applied or authoritative Review. The same exact-target/identity, canonical-answer, mapped readback, single-use authorization and no-replay gates remain.

Verification through `terminal`: run the repository's guarded `run_offline_tests.py tests/test_native_option_coverage.py tests/test_answer_coverage.py tests/test_prepare_live_job.py -q`, then the full guarded suite. The synthetic read-only orchestration regression must report `review_ready=false`, `submission_enabled=false`, and no field-evidence writes for an unavailable required option. This exercises the code seam without opening a browser or claiming a connected employer workflow.
