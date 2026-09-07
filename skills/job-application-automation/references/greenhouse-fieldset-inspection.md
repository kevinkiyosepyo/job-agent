# Greenhouse fieldset inspection

Use `terminal` with `prepare_job.py SAVED_HTML --page-url EXACT_OFFICIAL_URL --output PRIVATE_REPORT` for non-submitting inspection. This does not open a browser or advance an application, including when a canonical submission intent is unresolved.

1. For checkbox questions, inspect `choice_groups` as well as the flattened `fields`. An option label such as `Personal Projects` is not the question; the enclosing fieldset's unique direct legend supplies it.
2. Groups are scoped to the nearest fieldset and exact name. Missing or ambiguous legends are not guessed. Preserve exact option IDs and raw values; bracketed IDs are identifiers, not ready-made CSS selectors.
3. `required` reports fieldset ARIA requirement or native/ARIA input requirement markup. It does not establish minimum/maximum counts, live browser validity or saved selections. Do not select all options simply because multiple inputs have `required`.
4. `source=static_html` and `bound_values_verified=false` are strict evidence limits. Reacquire the exact rendered controls and their current option binding before any authorized fill. Do not infer checked values, upload bytes, Review authority, or acceptance from these records.
5. Keep unrelated inputs visible in the inventory. React Select can publish an unnamed required validation companion alongside its labelled combobox; this is not enough to declare an extra unanswered question, suppress validation, or infer visual hiding from ARIA alone.

## Preparation coverage

The preparation converter retains checkbox kind and collapses a uniquely named static checkbox group into one question only when its nonblank prompt, boolean requirement, unbound provenance, sibling kinds, option count and exact option-label multiset match. It retains the complete original group as `native_checkbox`; raw field inventory and option IDs/values are unchanged. Missing, mixed, duplicated or inconsistent group evidence leaves the original questions in place instead of guessing membership. Either the group requirement or any required sibling makes the collapsed question required.

A canonical fact is not a selected checkbox set. Known checkbox facts remain blocked with `checkbox_selection_unverified`; unknown required groups remain unknown, and optional unresolved groups may be skipped. Neither supplied options nor a claimed bound flag clears selection checks. This diagnostic has no checkbox-filling adapter and does not expand connected Review support. Reacquire and verify real selections through a separately supported, authorized path.

After handler or conversion changes, use `terminal` to run the repository's guarded `run_offline_tests.py` with `tests/test_checkbox_group_questions.py tests/test_greenhouse_fieldset_inventory.py tests/test_greenhouse_handler.py -q`, then the full guarded suite. Reconcile a real saved official capture independently of synthetic regression tests. Report inspected/filled/Review-verified/submitted/confirmed/notification-verified separately. Passing static tests never grants application authority.
