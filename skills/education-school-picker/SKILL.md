---
name: education-school-picker
description: Pick UC San Diego quickly in ATS school fields.
version: 1.0.0
author: Kevin Pyo, Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [jobs, ats, education, dropdowns, school]
    related_skills: [job-application-automation, ats-form-filling]
---

# Education / School Picker

Select Kevin's real school in ATS directories quickly and verify the bound value. Never spend more than 30 seconds searching one school field; use the real `Other` option instead of guessing another institution.

## When to Use

- A job application asks for school, university, college, or institution.
- A resume parser inserted an unverified school label.
- A custom combobox requires selecting a directory-backed school object.

Do not use for free-text-only education fields; enter the canonical school name directly and verify it.

## Canonical Answer

- Preferred rendered value: `University of California, San Diego`
- Acceptable exact variant when it is the directory's official entry: `University of California San Diego`
- Acceptable short official variant: `UC San Diego`
- Never substitute `San Diego State University`, another University of California campus, UCSD Extension, UC San Diego Health, or an approximate school.

## Thirty-Second Procedure

1. Start the 30-second budget after opening the live school control. Inventory whether it is a native select, custom combobox, autocomplete, or free-text field.
2. Inspect already-rendered/native options first. If the exact UC San Diego entry exists, select the real option and continue to Verification.
3. For a searchable picker, type exactly `University of California` as a filter. Do not start with `UCSD`; many directories index the full system name only.
4. Wait for the rendered option list once, then inspect every University of California campus option in that list. Select only the San Diego campus using the option row/radio itself.
5. Re-read the bound state immediately: selected chip/button text, hidden backing value when available, and inline validation state. Typed filter text is not selection evidence.
6. If the correct bound selection is not verified within 30 seconds, stop searching. Open the real option list and select `Other`, `Other School`, `School Not Listed`, or the tenant's equivalent.
7. If selecting `Other` reveals a dependent text field, enter `University of California, San Diego` and verify that field's exact value. If no dependent field appears, retain the verified `Other` selection; do not choose another campus.
8. Save/continue once and verify the server-rendered step or Review page. If the saved label changed, correct it once through the same procedure; otherwise mark the field human-required rather than looping.

## Control-Specific Fast Paths

### Native select

Read all option labels in one DOM pass. Select the exact canonical/accepted label by option value, dispatch the required input/change events, and read `selectedOptions` back.

### Custom combobox/autocomplete

Open the control, type the full-system filter once, inspect the current rendered options, click the exact San Diego row, and verify the selected chip/backing value. Never type-only and blur.

### Duplicate directory labels

When duplicate San Diego labels appear, inspect the backing option IDs and choose the entry that saves the canonical rendered name. If identity cannot be distinguished within the budget, use `Other`.

### Resume parser

Treat parser output as untrusted. Compare the saved school on the final Review page; Review is authoritative.

## Performance Rules

- One inventory, one full-system search, one exact selection attempt, then `Other`.
- Never retry alternative spellings for five minutes.
- Never search campus-by-campus.
- Cache only tenant control structure/selector knowledge, never an unverified option ID.
- Batch option extraction and verification in one browser operation when possible.

## Pitfalls

- Visible `University of California` text may only be the search query.
- Workday duplicate entries can save different labels.
- A selected-looking label can still have an empty backing value.
- `Other` must itself be a real option, not typed text.
- Never select a wrong UC campus merely to satisfy a required field.

## Verification

The field is complete only when one of these is server-saved:

1. An exact accepted UC San Diego directory entry, or
2. A real `Other` option, plus the canonical dependent text when the ATS provides it.

Confirm the validation error cleared and the Review page displays the intended school state. Record whether the result was `exact_directory_match` or `other_fallback`.
