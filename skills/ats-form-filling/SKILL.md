---
name: ats-form-filling
description: "Use when filling ATS job forms in a browser reliably."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [macos]
---

# ATS Form Filling

Use this skill when filling browser-based job application forms across Workday, Oracle Recruiting, and similar ATS flows.

## When to Use

- Multi-step job applications in a browser
- Forms with custom dropdowns, chips, date widgets, and resume upload controls
- Flows where visible text is not enough and the underlying selected value must truly bind

## Core Rules

1. Never claim an application is submitted without a verified confirmation page, candidate-home status, or application list entry.
2. Treat every custom dropdown as stateful UI, not a plain text box.
3. Treat every visible date value as suspect until the form accepts it and advances.
4. Re-read the page after every save/continue because many ATS forms silently reject values while leaving text on screen.

## Reliable Patterns

### 1) Dropdowns: select real options, do not just type

For ATS fields like:
- country
- school / university
- how did you hear about us
- salary bands / expectation ranges
- work authorization
- sponsorship
- consent questions

Do **not** rely on typing text into the control unless the control is explicitly a free-text field.

Preferred order:
1. Open the dropdown/prompt.
2. Click the actual option row in the rendered menu.
3. Confirm the selected chip / selected item / button label changed.
4. Save and verify the form no longer reports the field as missing.

Pitfall:
- A typed string can remain visible while the underlying selected value is still empty, causing the form to reject the field on submit.
- For `type=combobox` answer coverage, read `job-application-automation` → `references/combobox-option-coverage.md`. A known canonical fact is not verified option availability. Preserve `combobox_options_unverified` until the separate supported browser option/saved-state procedure provides its required evidence; never relabel the control as free text to clear a blocker.

### 2) School / university picker: 30-second fast path

Load `education-school-picker`. Search exactly `University of California` once, inspect the rendered UC campus list, and select the real `University of California, San Diego` option. Verify the selected chip/backing value. If the exact school is not bound within 30 seconds, select the real `Other`/`School Not Listed` option and enter the canonical school name only if a dependent text field appears. Never select another UC campus and never loop through alternate spellings.

### 3) Nested source pickers

Some ATS forms use a parent category and a child option. Kevin's required flow is:
- click the actual `Social Media` option (`Social Networking Site` on some tenants);
- wait for the dependent picker;
- click `Instagram`, with `Facebook` then `TikTok` as fallbacks.

Typing the parent label is only filtering and never satisfies the field. Verify both selected option states before continuing. A profile default is not usable when the actual native select lacks that option; do not invent another referral. Read `job-application-automation` → `references/native-option-coverage.md` for the installed fail-closed static coverage check. Its known entries are only option availability, never saved-answer or Review proof.

### 4) Combined sponsorship wording needs both timeframes

Read `job-application-automation` → `references/combined-sponsorship.md` for the recognized whole prompts. `Now or in the future` is not future-only: independently resolve current and future sponsorship facts, require both valid, then Yes if either is Yes. Missing/conflicting facts remain blocked; never infer legal answers from required Yes/No options. Verify the actual option and final Review.

### 5) Salary fields may be dropdown-backed even when they look text-like

For compensation questions, first check whether the field is a real dropdown or prompt. If it is, select a real option instead of typing a number.

### 6) Date widgets may require more than visible MM/YYYY text

Read `job-application-automation` → `references/experience-date-scope.md` before resolving short date labels. A generic education or availability `Start date month` is not an employment-start question. Require the correct section/record, not a company acronym appearing as a substring; repeated records remain ambiguous. The engine's exact employer-scoped mapping does not bind a widget or verify a saved date.

Even if month/year text appears on screen, the ATS may still consider the field empty until one of these happens:
- focus/blur cycle completes
- picker selection is made
- the control's internal value binding updates

Verification rule:
- If the page still reports `The field From is required` or similar, do not trust the visible date. Re-open the control and bind the date through the widget, not just by text injection.

### 7) Resume upload must be verified twice

For required resume fields:
1. Set the file through the actual file input.
2. Verify the filename appears in the UI.
3. After save/continue, verify the page says the file was uploaded successfully or still shows the file in the application-specific resume slot.

Do not assume an earlier autofill upload satisfies a later application-specific resume requirement.

### 8) React-backed controls can look native

Some custom ATS pages render ordinary `<select>` and `<textarea>` elements while React stores separate application and validation state. Visible DOM values or `innerText` option lists are not proof of a bound answer.

Reliable sequence:
1. Reacquire the live control after every rerender.
2. Use the control type's native prototype setter.
3. Dispatch the exact bubbling input/change event expected by the control.
4. Wait for rerender before changing another field.
5. For required textareas, complete a real focus/blur cycle or invoke the live field-level blur handler when documented by the ATS child.
6. Verify selected index/value, framework backing state when observable, error clearance, and actual step/URL transition.

### 9) Use candidate-home verification after submit

For Workday- or Oracle-style portals, submission can often be verified from:
- candidate home
- my applications
- active applications
- status text like `Under Consideration`
- requisition number plus applied date

This is acceptable confirmation when the portal lists the exact application after submission.

## Kevin-Specific Defaults For ATS Applications

Use these only when the live question matches and the user has not overridden them:

- Desired pay: `$20/hour` or `$20k annual` when the application requires a compensation answer
- Source / how heard: default to `Social Media`, then pick `Instagram` or `Facebook` if the form requires a concrete platform
- Education timing: `B.S. Data Science`, `Sep 2024 - May 2028`
- Address to use for applications: read `profile.json -> contact.location` (street, city, state, zip). Never hardcode the street address in a skill file — this repo is public.

## Verification Checklist

Before advancing each page:
- required fields no longer show validation errors
- dropdown-backed fields show a real selected item, not just typed text
- date fields are accepted by the form, not merely visible
- application-specific resume slot is satisfied when required

Before final answer to the user:
- cite the exact verified status page / confirmation text / application list entry

## References

- See `references/disney-bny-quirks.md` for concrete examples of dropdown, nested-source, date, and portal-verification quirks found in live ATS sessions.
- Read `references/eligibility-screening-before-submit.md` BEFORE spending a submit. A submit is irreversible and rate-limited; screen the posting's own eligibility text first rather than discovering a disqualifier after the fact.
- Read `references/hidden-tab-and-silent-bind-failures.md` when driving a background CDP worker. A hidden tab discards trusted mouse input and a bind can fail silently, so verify the tab is rendered and the bind is live before trusting any field write.
