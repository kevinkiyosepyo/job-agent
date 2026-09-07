# Exact combined sponsorship questions

Use for these complete prompts:

- `Will you now or will you in the future require employment visa sponsorship?`
- `Will you now or in the future require sponsorship?`
- `Do you now, or will you in the future, need sponsorship from an employer in order to obtain, extend or renew your authorization to work in the United States?`

The semantic field is `sponsorship_now_or_future`, not just `sponsorship_future`. The canonical resolver independently resolves both existing `sponsorship_now` and `sponsorship_future` facts. Both must be present and valid; Yes in either yields Yes, both No yields No. Missing or conflicting facts remain blocked, even if an answer file, knowledge entry or only a combined extension supplies a proposed answer. A duplicated explicit combined profile value must agree with the two grounded timeframes.

Do not treat these narrow whole-prompt aliases as a classifier for arbitrary legal statements. Negated, compound, conditional or explanation questions require separate grounding. Current-only/future-only prompts retain their existing separate semantics. No user facts or immigration status are inferred from the employer wording.

`terminal`: run the guarded `run_offline_tests.py tests/test_combined_sponsorship.py tests/test_sponsorship_extended_prompt.py tests/test_question_engine.py tests/test_canonical_answers.py -q`, then the full guarded suite. The regression covers the former current=Yes/future=No false-No outcome, missing/conflicting input and independent canonical Review rejection of contradictory proposed answers. Native radio/select coverage still requires one actual usable option; recognized wording is not a bound selection or employer eligibility.

The saved Hermeus and Virtu pilots exercise exact recognized wording. Virtu's public API option schema and unfilled HTML combobox are not rendered/bound selection evidence. A positive raw-label coverage result is not a live form, complete preparation, Review or submission certification and cannot release an uncertain submission intent. School alternatives, GPA bands, future availability, offers and preferences need their own grounding; this alias does not answer them.
