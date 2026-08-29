---
name: ats-form-filling
description: "Use when filling ATS job forms in a browser reliably."
version: 1.0.0
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

### 2) School / university picker: 30-second fast path

Load `education-school-picker`. Search exactly `University of California` once, inspect the rendered UC campus list, and select the real `University of California, San Diego` option. Verify the selected chip/backing value. If the exact school is not bound within 30 seconds, select the real `Other`/`School Not Listed` option and enter the canonical school name only if a dependent text field appears. Never select another UC campus and never loop through alternate spellings.

### 3) Nested source pickers

Some ATS forms use a parent category and a child option. Kevin's required flow is:
- click the actual `Social Media` option (`Social Networking Site` on some tenants);
- wait for the dependent picker;
- click `Instagram`, with `Facebook` then `TikTok` as fallbacks.

Typing the parent label is only filtering and never satisfies the field. Verify both selected option states before continuing.

### 4) Salary fields may be dropdown-backed even when they look text-like

For compensation questions, first check whether the field is a real dropdown or prompt. If it is, select a real option instead of typing a number.

### 5) Date widgets may require more than visible MM/YYYY text

Even if month/year text appears on screen, the ATS may still consider the field empty until one of these happens:
- focus/blur cycle completes
- picker selection is made
- the control's internal value binding updates

Verification rule:
- If the page still reports `The field From is required` or similar, do not trust the visible date. Re-open the control and bind the date through the widget, not just by text injection.

### 6) Resume upload must be verified twice

For required resume fields:
1. Set the file through the actual file input.
2. Verify the filename appears in the UI.
3. After save/continue, verify the page says the file was uploaded successfully or still shows the file in the application-specific resume slot.

Do not assume an earlier autofill upload satisfies a later application-specific resume requirement.

### 7) Use candidate-home verification after submit

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
- Address to use for applications: `10256 Eagle Nest Ct, Fairfax, VA 22032`

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
