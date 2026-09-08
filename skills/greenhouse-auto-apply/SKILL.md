---
name: greenhouse-auto-apply
description: "Fill and verify Greenhouse job application forms."
version: 1.1.0
author: Kevin Pyo, Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [jobs, greenhouse, ats, browser, applications]
    related_skills: [job-application-automation]
---

# Greenhouse Auto-Apply

Fill Greenhouse forms through Kevin's approved Chrome CDP session, verify every value, and submit only when the application is complete and no manual gate remains.

## When to Use

- The application URL contains `greenhouse.io`, `boards.greenhouse.io`, or `job-boards.greenhouse.io`.
- Do not use for Workday, Ashby, Lever, SmartRecruiters, BambooHR, or custom ATS pages.

## Prerequisites

- Profile: `~/Documents/job-agent/profile.json`.
- Primary resume path is read from `profile.json`; do not guess or silently substitute another file.
- Notifier: `~/Documents/job-agent/notifier.py`.
- Discover the approved normal Chrome debugging connection rather than assuming a port such as 18800. Load `authenticated-browser-workflows` → `references/normal-chrome-routing-and-cdp.md`; reuse the task's persistent approved connection. Chrome UI debugging may expose only the WebSocket named by `DevToolsActivePort` while `/json/list` returns 404.
- The user has authorized access to this existing Chrome profile.

## Procedure

1. Read `profile.json` and stat the selected resume. Do not open or query the Google Sheets tracker; use the current task URL and live portal/current application state for duplicate detection unless Kevin explicitly requests tracker synchronization.
2. If the employer is Meta, Amazon, Apple, Netflix, Google, Microsoft, or a clear subsidiary, do not apply. Call `notifier.py maango` with company, role, and URL, then stop.
3. Open the exact listing in the approved Chrome session. Confirm the title, company, location, and that the posting is still accepting applications.
4. Inventory all visible and conditional questions before typing. Use DOM labels and the accessibility tree; never infer a question from screen position alone. Run `greenhouse_handler.py` on the untouched form and consume `control_hints.prefilled_ids` plus `control_hints.education_groups`. Record the actual education index (`--0`, `--1`, etc.) before any write.
5. Normalize prefilled values before adding new data:
   - Re-read every existing plain value and selected React chip.
   - Preserve exact correct values.
   - Replace incorrect or duplicated text with the adapter's native-setter `replace_text`; never call generic append-style typing on a populated field.
   - Re-inventory after resume parsing or any education add/remove because Greenhouse can renumber control IDs.
6. Upload the resume without a native picker when possible:
   - Locate the actual `input[type=file]` with `DOM.querySelector`.
   - Call CDP `DOM.setFileInputFiles` with the absolute resume path.
   - Capture the browser File metadata promptly and verify the rendered Greenhouse filename against the exact selected local file. Some modern Greenhouse forms remove the resume input immediately after successful attachment; a missing `#resume` after `DOM.setFileInputFiles` is not an upload failure. Inspect the unique `[aria-labelledby="upload-label-resume"]` group and its `.file-upload__filename p`, plus actual attachment state when available. Never repeat a successful upload just because the original node disappeared, and never fabricate missing File metadata.
   - Wait for parsing to settle, then re-inventory before entering text: parsing can populate name/contact fields and renumber education IDs. Generic `Input.insertText` can append to parser-filled values or a previously focused field. Use the learned native-setter replacement and exact React Select helpers, and verify both the displayed value and actual bound state before proceeding.
7. Fill identity and contact fields from `profile.json` with the adapter's exact replacement action. Focus each control, replace the whole old value, blur, and re-read it; never append.
8. For Greenhouse React Select controls, use the learned `react_select_exact` operation with separate `search_text` and `exact_option`. The helper clears stale selections, filters once, waits for the asynchronous list, clicks one exact visible option, and verifies `.select__single-value`. Fail closed if the exact option is absent. Use `[id^='school--']`, `[id^='degree--']`, and `[id^='discipline--']` only after handler inventory proves each selector is unique.
9. Dismiss Chrome address/autofill overlays before selecting Greenhouse options. Distinguish browser UI suggestions from page-owned listbox options through the accessibility tree.
10. Answer factual screening questions only from `profile.json` or the resume. Defaults: US work authorization Yes, sponsorship No, willing to relocate Yes, graduation Spring 2028. Do not invent years of experience, compensation, clearances, or domain expertise.
11. Demographics, when asked and optional: Male; Asian; not a protected veteran; disability Decline to answer. Skip optional cover letters. Do not consent to unrelated talent-retention programs unless required.
12. Review the whole form from top to bottom. Confirm required fields, exact resume filename, no duplicated country code, no answer routed into the preceding combobox, and no validation errors.
13. If a visible CAPTCHA challenge, email verification, identity verification, assessment, or genuinely unknown question appears, preserve the prepared tab and call `notifier.py captcha` or `notifier.py question`. Do not mark it submitted. Dormant invisible reCAPTCHA plumbing is handled under Pitfalls below.
14. Otherwise click Submit once. Verify a Greenhouse confirmation page or unambiguous success message. A click, spinner, or disabled button is not confirmation.
15. Only after confirmation send `notifier.py applied` and read back the Discord result. Do not open or update the Google Sheets tracker unless Kevin explicitly requested tracker synchronization for this application.
16. On failure, leave the tab in the most recoverable state, record the exact blocker, and send `notifier.py failed`.

## Static search-only redirects

Read `job-application-automation` → `references/search-only-employer-pages.md` when a saved official URL yields only site search. A GET `/search` box is not an application; preserve requested/effective URLs, inspect `form_evidence`, and do not interpret prepare CLI exit 2 as a closed role. The narrow detector does not certify other shells or rendered form availability.

## Static combobox coverage

Read `job-application-automation` → `references/combobox-option-coverage.md` before interpreting answer coverage for a collapsed combobox. A known profile fact is not proof the real option exists; the narrow preparation diagnostic blocks it with `combobox_options_unverified`. API options and claimed bound flags do not clear that check. This does not expand connected support or replace the actual option-selection/saved-state procedure.

## Static multiselect inspection

Read `job-application-automation` → `references/modern-greenhouse-multiselect.md` for `control_hints.react_multiselects`. A unique-ID combobox inside an explicit multi-value container is a static chip-control hint, not a single select or verified option set. API multi-value questions can instead be checkbox groups; inspect actual markup. Do not use a single-chip clearing helper on multi-value controls. Hints remain unbound and do not expand connected support.

## Static modern-header identity

Read `job-application-automation` → `references/modern-greenhouse-static-location.md` when saved modern Greenhouse markup has a blank or prose-derived location. The shared inspector uses a unique scoped `.job__header` / `.job__location` value, excludes sibling SVG text and leaves ambiguous modern markup unknown. This is static identity, not rendered availability or proof of US eligibility; submission and Review gates remain unchanged.

## Static fieldset inspection

For saved Greenhouse checkbox schemas, read `job-application-automation` → `references/greenhouse-fieldset-inspection.md`, including its preparation-coverage procedure. A uniquely matched static group becomes one question without guessing a selected set; known checkbox facts remain blocked by `checkbox_selection_unverified`. The inspector keeps the enclosing question legend separately from option labels/IDs/raw values in `choice_groups`. These records are static and unbound; they cannot establish saved selections, actual validity or permission to submit. A required group does not mean select every option. Keep unnamed React Select validation companions in inventory rather than guessing an extra unanswered question.

## Static upload question inspection

Read `job-application-automation` → `references/modern-greenhouse-upload-questions.md` when the native file input has only an `Attach` label. A unique scoped upload wrapper can supply the actual document question and an additive requirement. Preserve specific control labels and separate optional documents. Static question recovery is not attachment, byte provenance or Review evidence; unsupported shapes retain raw inventory.

## CDP Upload Pattern

Use `browser_exec` with the real tab selected:

```python
doc = cdp('DOM.getDocument', depth=1)
node = cdp('DOM.querySelector', nodeId=doc['root']['nodeId'], selector="input[type=file]")
cdp('DOM.setFileInputFiles', nodeId=node['nodeId'], files=[resume_path])
name = js("document.querySelector('input[type=file]').files[0]?.name")
```

If more than one file input exists, identify the resume input from its label/accept attributes; never use the first input blindly.

## Pitfalls

- Never treat a bootstrapped `confirmation_message` or translated future-success string in script data as employer confirmation. Modern untouched Greenhouse pages can contain these strings alongside a blank application. Inspect the real post-submit state and preserve the original intent; a static page classifier is not authoritative acceptance evidence.
- Chrome autofill can cover the real listbox and change accessibility indices.
- Greenhouse controls can retain focus after a selection; click the next field directly.
- If a country selector already supplies `+1`, enter only the local phone digits.
- A native picker closing does not prove upload success; the filename does.
- Never solve or bypass a CAPTCHA. A hidden `g-recaptcha-response`, invisible Enterprise key, or reCAPTCHA iframe that is part of Greenhouse's normal submit plumbing is not by itself a human gate: do not manipulate it, submit normally once, and inspect the result. Stop only if a visible checkbox/image/audio challenge or explicit human-verification prompt appears. On a verified confirmation page, confirmation evidence takes precedence over a handler's residual invisible-CAPTCHA detection.

## Verification

- Live portal/current-task duplicate check returned clear without opening Sheets.
- Every required field has a re-read value and no validation error.
- Resume filename equals the selected local basename.
- MAANGO employers were notification-only.
- Submitted status exists only with a confirmation page/message.
- Discord notification agrees with the verified final state. Tracker verification applies only when Kevin explicitly requested tracker synchronization.
