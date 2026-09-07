# Employer-scoped experience month answers

Use when a short date label, education date widget, availability question or employer-specific experience prompt is being mapped to a work-history month.

The question engine recognizes only the employer-specific wording `What month did you start at <employer>?` for experience-start-month lookup, with case/display-whitespace normalization and the ordinary trailing question/required markers. The entire employer target must match a normalized profile company name or its whole acronym. A letter appearing anywhere in `Start date month` is not an employer match. Generic education/availability prompts and compound/conditional suffixes do not borrow an experience date.

Require exactly one matching experience record with a supported month-bearing start value. Repeated employment records or colliding acronyms remain unknown even when their month values agree; never choose the first record. A year-only start does not prove a month. Historical answer documents cannot fill missing material experience dates.

This repair only prevents false known answers. It does not introduce education/availability date mapping, choose an option, bind a date widget, update a canonical fact or weaken final Review. For real date fields, inventory the enclosing section and record index, use the corresponding canonical record, bind the real control, save and independently verify. Keep unsupported contexts blocked rather than relying on a coincidentally equal month.

Through `terminal`, run the configured interpreter with `run_offline_tests.py tests/test_experience_date_scope.py tests/test_question_engine.py -q`, then the full guarded suite. Replay complete saved forms: generic education start-month questions should leave `known`, without changes to other questions, field schema, non-date answers or stage authority. Do not print raw private employment dates in public reports.
