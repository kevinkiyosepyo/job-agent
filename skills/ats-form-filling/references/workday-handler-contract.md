# Workday Executable Handler Contract

This reference captures the validated non-submitting Workday inspection contract for ATS automation. It complements browser-filling instructions: use it when building or invoking deterministic handlers, fixture tests, preflight checks, or queue workers.

## Page-state classification

Classify the rendered page before any mutation:

- `listing` — official posting with no application fields and a rendered Apply action.
- `application_start` — Workday's choice page before the wizard.
- `application` — wizard fields/steps are rendered.
- `confirmation` — normalized success evidence is present.

Do not infer state from the URL alone. Workday may keep the same job URL while rendering different React surfaces.

Useful Workday `data-automation-id` values validated on real pages:

- `jobPostingHeader` — role title on listing pages
- `locations` — rendered locations
- `requisitionId` — requisition ID
- `adventureButton` — Apply entrypoint
- `utilityButtonSignIn` — Sign In entrypoint
- `autofillWithResume` — Autofill with Resume start action
- `applyManually` — Apply Manually start action
- `useMyLastApplication` — Use My Last Application start action

Treat the action `href` as data. A background/native click may be a no-op; verified navigation to the exact rendered link is acceptable when the task authorizes opening the non-submitting application start surface.

## Required structured output

A handler/preflight result should expose at least:

```json
{
  "page_type": "application",
  "page_url": "https://tenant...",
  "tenant": "tenant.wd1.myworkdayjobs.com",
  "role": "...",
  "location": "...",
  "steps": [],
  "fields": [],
  "entrypoint": {},
  "start_actions": {},
  "uploaded_resume_verified": null,
  "manual_gate": null,
  "manual_gates": [],
  "save_draft_available": false,
  "parse_issues": [],
  "safe_to_prepare": false,
  "confirmation_text": null,
  "confirmation_reference_id": null
}
```

`safe_to_prepare` is true only on an application surface when:

- no CAPTCHA/email-verification/assessment gate is present;
- no resume-parser mismatch is unresolved;
- expected resume verification is not false.

Listing, application-start, and confirmation surfaces are not themselves ready-to-prepare forms.

## Resume parser verification

Workday-parsed values are untrusted. Compare parsed and canonical values field by field and report mismatches with:

- section
- field
- parsed value
- expected value

Known high-risk fields are school, degree, major, GPA, job title, employer, dates, email, and phone. Do not silently repair a conflict without preserving the mismatch in the preflight/audit result.

Resume upload verification remains separate: verify the exact basename in the rendered application-specific resume slot. An earlier autofill upload does not prove the later wizard slot is satisfied.

## Manual gates

Report every simultaneous gate, not only the first:

- CAPTCHA/hCaptcha/reCAPTCHA
- email verification
- assessment/take-home
- identity verification when present

Keep a `manual_gate` first-item compatibility field plus the complete `manual_gates` array. If any gate exists, fail closed; Save as Draft is a recoverability signal, not permission to continue or submit.

## Confirmation evidence

A button click, navigation, spinner, or disabled Submit button is not evidence. Require normalized success text such as application received/submitted or thank-you language. Extract a Workday reference/confirmation ID when rendered and bind it to the sanitized submission artifact, tracker read-back, and notification reconciliation.

## CLI behavior

Machine-oriented handlers should emit JSON. Exit nonzero (for example `2`) when manual gates, parser mismatches, or explicit resume verification failures block preparation. Inspection-only listing/start/confirmation states may exit successfully while keeping `safe_to_prepare: false`.

## Test matrix

Maintain harmless fixtures for:

1. listing + Apply/Sign In/requisition metadata
2. application-start action choices
3. wizard fields/steps + uploaded resume read-back
4. parser mismatches + Save as Draft
5. simultaneous manual gates
6. verified confirmation + reference ID
7. integration through the multi-ATS preflight dispatcher

Add a real non-submitting snapshot test when practical. Validated example behavior included an active Workday listing, its `/apply` start page, and all three start-action URLs; no resume upload, account creation, or submission occurred.

## Safety boundary

The executable inspector is not the submitter. Browser mutation stays in the approved ATS workflow and must re-read each stateful control. Never let a handler's successful parse be treated as proof that a real browser field is selected or an application is submitted.
