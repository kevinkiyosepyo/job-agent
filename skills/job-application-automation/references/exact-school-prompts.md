# Exact school prompt recognition

Use when a native form asks exactly `Name of School`. `QuestionAnswerEngine` now maps this whole prompt to the existing canonical `school` fact. Its existing case/whitespace/trailing question-mark normalization applies; it does not substring-match prior-school, high-school, compound or conditional questions.

Read the canonical profile under the umbrella. Missing and conflicting school facts remain unknown/conflict. Native option coverage still requires the actual intended option; recognizing the question is not permission to choose a similar university or guess a directory value.

For real directory spellings, load `education-school-picker`. Its approved campus variants require the separately grounded tenant option-mapping/readback path; this question alias does not implement automatic alias normalization or change canonical Review answers. A directory spelling mismatch can remain `answer_not_in_native_options` rather than `unknown_question` until that path is verified. This is an automation limitation, not employer ineligibility.

Verification through `terminal`: run the guarded `run_offline_tests.py tests/test_school_prompt_coverage.py tests/test_question_engine.py tests/test_answer_coverage.py -q`, then the full guarded suite. Preserve missing/duplicate/disabled option and canonical profile checks. No browser, saved-state or Review authority comes from the static test.
