# Radio question coverage from static Lever markup

Use when a saved Lever pilot has multiple radio inputs for one required question. Through `terminal`, run the guarded tests for `test_radio_option_coverage.py` and `test_native_option_coverage.py`, then the full guarded suite.

The preparation inventory collapses a radio group only when one explicit static group matches the nonempty name, type and exact question label; every same-name field must be a radio with that label, and the option/field counts must agree. Duplicate cards/names, mixed control types or partial schemas remain unresolved rather than merged. Required status is the union of the original inputs, not permission to answer Yes.

`native_radio` carries option definitions to the existing fail-closed native-option coverage check. A known canonical fact needs exactly one matching label, a unique explicit nonempty raw value and boolean disabled metadata. Missing, disabled, ambiguous or malformed options remain blocked. Optional unavailable groups can skip once without gaining known-answer evidence. Unknown canonical facts and generic prompts such as `Select One` remain unknown; card headings are context, not automatic answer mappings.

Lever radio options add `disabled` metadata from the input or an enclosing disabled fieldset. This is deliberately conservative: the first-legend exception is not certified, nor are CSS/ARIA/JavaScript visibility and interactability. Checkbox and native-select inventories remain separate. No checked attribute is promoted to a bound answer.

These are static schema and fact-availability results, not selected controls, saved answers, upload-byte provenance, independently grounded Review or submission authority. A currently enabled/checked browser radio still requires exact live option binding and final Review. This change does not enable a new connected ATS family or change no-replay/ledger gates.
