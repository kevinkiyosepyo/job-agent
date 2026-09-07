# Static employer search-only pages

When an official application URL redirects to an employer listing, preserve both requested and effective URLs plus source-byte hashes. HTTP 200 is retrieval success, not proof of an application form.

Use `terminal` to run `prepare_job.py SAVED_HTML --page-url EXACT_ATS_URL --output PRIVATE_REPORT`. The saved Greenhouse inspector recognizes the narrow case where every inventoried control is an input of type `search` inside an explicit GET `/search` form. It reports `page_type=listing`, `form_evidence.status=search_only`, `rendering_verified=false`, and `safe_to_prepare=false`. The prepare CLI returns 2; this is an incomplete preparation surface, not a closed job. Manifest preflight shares the predicate and does not count that surface as an application.

- Keep the search control in inventory. Never fill personal data into it or delete it to make validation pass.
- The predicate is deliberately narrow. An absent marker does not prove a complete form; other search forms, POSTs, hidden controls and dynamic shells are not certified by this case.
- A security gate remains a gate; a recognized confirmation is not overwritten by search-only classification. All such static text evidence still needs independently grounded live confirmation before any application status change.
- Fetch metadata, official listing identity and actual form availability are separate. On a recognized search-only shell, the saved handler discards em-dash prose guesses for company/location; an explicit Greenhouse `Job Application for ... at ...` document-title company is retained. The legacy manifest inspector clears its prose-derived identity too. A blank company/location means unavailable evidence, not an anonymous employer or unlocated role. This narrow correction does not validate identity on other surfaces; retain the independently verified listing source.
- When browser access is unavailable, record incomplete rendered coverage. Do not create an isolated browser, change permissions, bypass a security denial or grant submit authority to obtain a cleaner result.

Verification: run the guarded `run_offline_tests.py tests/test_greenhouse_shell_identity.py tests/test_greenhouse_search_only.py tests/test_ats_preflight.py tests/test_greenhouse_handler.py -q`, then the full guarded suite through `terminal`. Replay the exact saved public bytes and check the output, exit status and provenance. Fixtures are synthetic test data, not new official pilots or applications.
