# Modern Greenhouse static location

Use `terminal` with `prepare_job.py SAVED_HTML --page-url EXACT_OFFICIAL_URL --output PRIVATE_REPORT` for saved public-page inspection. The rich handler and legacy manifest preflight use the same narrow location reader:

- One `.job__header`, one descendant `.job__location`, and one direct child `div` supply the static value. A sibling SVG icon is not location text. Concatenate decoded text fragments before display-whitespace normalization so inline punctuation and word adjacency remain intact.
- Multiple headers/containers/value divs, or an incomplete recognized modern header, leave location unknown. Never choose by position or fall back to arbitrary em-dash prose in that case.
- Pages without a modern header retain legacy parsing; that fallback is not newly certified. Recognized search-only employer shells still suppress identity guesses and remain non-preparable.
- Do not infer a country from an ambiguous city. A recovered city string can still require geographic verification; a parsed location is not work authorization or full eligibility.
- This is saved, static identity evidence only. It does not prove current visibility, employer availability, complete controls, saved answers, Review provenance or acceptance. Existing CAPTCHA/assessment/confirmation/submission gates are unchanged. Preserve the source URL and byte digest separately.

Verification through `terminal`: `run_offline_tests.py tests/test_greenhouse_modern_location.py tests/test_greenhouse_handler.py tests/test_ats_preflight.py -q`, then the full guarded suite. Replay the exact saved page and verify location plus unchanged role/company, option inventory and disabled submission. Do not launch a browser to complete this static regression.
