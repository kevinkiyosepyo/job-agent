---
name: workday-auto-apply
description: "Fill and verify Workday job application wizards."
version: 1.0.0
author: Kevin Pyo, Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [jobs, workday, ats, browser, applications]
    related_skills: [job-application-automation]
---

# Workday Auto-Apply

Complete Workday's tenant-specific wizard in Kevin's approved Chrome profile. Treat every tenant and parsed resume as untrusted until values are verified.

## When to Use

- URLs contain `myworkdayjobs.com`, `myworkdaysite.com`, or a Workday recruiting tenant.
- Do not use for Greenhouse, Lever, Ashby, or Oracle career sites.

## Prerequisites

- Profile: `~/Documents/job-agent/profile.json`.
- Tracker: `~/Documents/job-agent/tracker.py`.
- Notifier: `~/Documents/job-agent/notifier.py`.
- Approved Chrome CDP endpoint: `http://127.0.0.1:18800`.
- Primary resume is the path stored in `profile.json`.

## Executable Handler Contract

For every Workday tenant/application, load this skill and use the verified local handler before browser mutation:

- Handler: `~/Documents/job-agent/workday_handler.py`
- Tests: `~/Documents/job-agent/tests/test_workday_handler.py`
- Safe fixtures: `~/Documents/job-agent/fixtures/workday*.html`
- Multi-ATS preflight: `~/Documents/job-agent/ats_preflight.py`

The handler recognizes Workday `data-automation-id` surfaces including:

- `jobPostingHeader` → role title
- `locations` → rendered locations
- `adventureButton` → Apply entrypoint
- `utilityButtonSignIn` → Sign In entrypoint
- `requisitionId` → requisition ID after removing the `job requisition id` prefix
- `autofillWithResume`, `applyManually`, and `useMyLastApplication` → explicit non-submitting start actions

It distinguishes `listing`, `application_start`, `application`, and verified `confirmation` pages. It inventories wizard steps and labeled fields, verifies the exact uploaded resume filename, reports Workday parser mismatches against source values, detects Save as Draft, collects all simultaneous CAPTCHA/email-verification/assessment gates, fails closed on unsafe preparation, and extracts confirmation reference IDs.

Run fixture inspection with:

```bash
python ~/Documents/job-agent/workday_handler.py FIXTURE.html \
  --page-url 'https://tenant.wd1.myworkdayjobs.com/.../job/...' \
  --expected-resume-basename 'EXPECTED_RESUME.pdf'
```

Exit code `2` means a manual gate, parser mismatch, or resume read-back failure blocks preparation. Never reinterpret that as success. Run `python -m pytest tests/test_workday_handler.py -q` from `~/Documents/job-agent` after handler changes.

Each employer is a separate Workday account boundary. Prefer a verified existing authenticated tenant session, then any indexed tenant-specific Keychain service `hermes-job-agent-tenant-<exact-hostname>`. Otherwise create the tenant account for `kevinkpyo@gmail.com` with the account-creation value stored in macOS Keychain service `hermes-job-agent-workday-universal`, then activate/sign in and verify the exact tenant/job route. If sign-in rejects the value or the account already exists, use Forgot Password once, retrieve only the newest exact tenant reset link/code through the approved read-only Gmail flow, set New Password and Confirm Password from Keychain service `hermes-job-agent-reset-universal`, verify explicit reset success, sign in again, and save that verified current value under the exact tenant-specific service for future runs. Never copy either value into memory, skills, profile files, logs, Git, Discord, tracker data, or user-facing output. Verify Keychain records by metadata only; if missing or denied, leave the tenant tab open and ask Kevin to authenticate directly.

Account creation lessons:

- Workday account activation and password-reset emails may have empty bodies in the simple Gmail wrapper. Search broadly by subject/sender—including employer-specific senders such as `myworkday@<employer-domain>`—then use read-only Gmail API `format=raw` MIME parsing to extract only the exact tenant activation/reset URL. Always choose the newest message: reset links can expire quickly or be invalidated by a later request. Open the newest link and complete reset, sign-in, and redirect verification without unnecessary delay.
- Activation must be verified before sign-in. A visible `Account Activated` or `Password has been reset` state is evidence; clicking alone is not.
- Some Workday submit/sign-in/reset buttons are covered by a visible `data-automation-id="click_filter"` overlay. Clicking the underlying hidden button can be a no-op. Inspect `document.elementFromPoint(...)` and invoke the visible overlay whose `aria-label` matches the intended action. Reacquire its bounding box after every scroll/rerender; stale coordinates can miss even when they were correct one call earlier. For password reset, require the visible `Password has been reset` state before attempting sign-in.
- Workday React controls can display values set through DOM mutation without committing them to application state. Use focused CDP/browser input events, then save and verify the server-rendered Review page. Date spinbuttons may rerender after each digit; refetch IDs and verify month/year after every change.
- Never trust parser output. The Medtronic flow produced UC Davis, wrong start months, merged descriptions, and an incomplete extra education record. Correct data from the resume/profile, save it, and verify every corrected month, title, description, school, GPA, disclosure, and answer on Review.
- Workday can retain an older account resume while accepting a new upload. Read `profile.json -> resume.primary` at the start of every application and use its exact current path and basename; never hardcode a filename learned in an earlier session. Reject every path in `resume.do_not_use_for_applications`. If multiple attachments appear, verify the final Review filename and file size match the current primary resume before Submit.
- Workday multiselect answers are option-backed state, not free text. Typing is allowed only to filter/search. Always click the exact rendered option and verify the selected chip/button text before leaving the control.
- Generic browser `fill_input` may append to a populated React input instead of replacing it. After every write, read the actual value. For replacement, focus the live control, select all, use CDP `Input.insertText`, blur with a real Tab event, and verify the exact value before saving.
- Workday school-directory search may not query until Enter is dispatched after typing. Search the exact campus name, inspect all duplicate rendered options, click the option's actual radio/row, and verify the bound selected chip. Duplicate options can save different labels, including misspellings; the server-rendered Review page is authoritative.
- A successful tenant account creation can redirect back to Sign In while the account still requires email verification. Retrieve only the exact activation URL through read-only Gmail MIME parsing, verify activation via the `/login/ok` state, then sign in with the Keychain credential and confirm the application resumes at the intended job.
- **How Did You Hear About Us is a two-step dropdown flow:** first select the real `Social Media` option (some tenants label it `Social Networking Site`); then, when the dependent follow-up appears, select `Instagram`, with `Facebook` and `TikTok` as fallbacks. Never type `Social Media` and move on—the typed text can clear on blur while the required state remains unset.
- Preserve the parent selection before handling the dependent social-network question. Re-inventory the page after selecting the parent because Workday reveals conditional controls dynamically.
- The first fully learned tenant took longer because account creation, activation, password reset, parser repair, click-overlay discovery, and server-state corrections were being discovered. Reuse these verified procedures on later tenants: preflight account/login first, use Keychain credential, activate via read-only email link, upload only the profile's current primary resume, correct parser output using native input, handle dropdowns by real option clicks, and verify Review. Do not repeat exploratory retries already documented here.
- **Canonical-route recovery:** if the resume-start route or a long-lived React page becomes inconsistent, navigate to the authenticated canonical `/apply` route for the exact requisition. Let it render server-saved state, then resave completed steps in order. This can remove the resume-start shell, rebuild the wizard, and expose which answers were actually persisted.
- **Browser target recovery:** a Browser Use target can drift to `about:blank`, another Chrome tab, or an unrelated SSO page, and a harness daemon can time out. Preserve the Workday account/draft, use a fresh named browser session when the old daemon hangs, navigate the exact URL, and keep delayed render inspection in the same browser call so tab selection does not drift between calls.
- **Persistence over premature handoff:** repeated nudges can be appropriate when the remaining failures are recoverable UI state, delayed email, session drift, or transient Workday errors. Keep working until confirmation. Stop only for a real CAPTCHA/security gate, missing material fact, or user-only action—not because the first synthetic interaction failed.

## Procedure

1. Read the profile, verify the exact `resume.primary` file exists and is not in `resume.do_not_use_for_applications`, and check the tracker for the exact URL and normalized company/role. Stop on a duplicate.
2. Route Meta, Amazon, Apple, Netflix, Google, and Microsoft (including clear subsidiaries) to Discord with `notifier.py maango`; do not apply automatically.
3. Open the listing and verify it is active. Record company, role, location, requisition ID, salary, and tenant hostname.
4. Select the fastest truthful path. Reuse a verified tenant session first. Otherwise create/sign in as `kevinkpyo@gmail.com` using only the Keychain account-creation service `hermes-job-agent-workday-universal`. If the account already exists or sign-in rejects that value, use Forgot Password once, retrieve only the newest exact tenant reset link/code through the approved read-only Gmail workflow, set and confirm the replacement value from Keychain service `hermes-job-agent-reset-universal`, verify explicit reset success, then sign in and confirm the application resumes at the intended requisition. Never embed, print, save, or transmit either secret through skills, memory, files, logs, chat, Discord, or tracker data. CAPTCHA/passkey/device-trust gates remain human-only.
5. Work through the wizard in order: My Information, My Experience, Application Questions, Voluntary Disclosures, Review, Submit. After each Continue, verify the step changed and no validation errors remain.
6. In My Information, fill contact and address data from `profile.json`. If a required ZIP, street, state of driver's license, or other missing fact is not available, notify Kevin instead of inventing it.
7. Upload the resume using the exact Workday resume input and CDP `DOM.setFileInputFiles`. Verify the browser file object and rendered filename.
8. Workday parsing is not authoritative. Compare every parsed job title, employer, date, school, degree, GPA, skill, email, and phone to the profile/resume. Correct bad parses and delete hallucinated or duplicated entries.
9. Do not add experience absent from Kevin's resume. Preserve present-tense jobs and accurate month/year granularity; do not fabricate exact dates when only years are known.
10. Answer conditional questions from `profile.json`: US authorization Yes, future sponsorship No, age 18+ Yes, relocation Yes, graduation Spring 2028. Re-scan after each answer because Workday may reveal new controls.
11. Optional cover letter: skip. Compensation: use `Open to discuss` if text is accepted; if a number is mandatory and the posting provides no defensible range, ask Kevin.
12. Voluntary disclosures: Male, Asian, not a veteran, disability Decline to answer. Complete required acknowledgments only after reading their visible text; do not opt into unrelated communications by default.
13. Use Save as Draft whenever an interruption, session warning, assessment, or unknown question appears. Workday sessions can expire in 15–30 minutes. Prefer Kevin’s approved normal Chrome profile and do not migrate a healthy live draft merely for convenience. If a Browser Use session is already carrying the authenticated draft, preserve and recover it with the canonical-route and fresh-session procedures above. Continue through recoverable UI/session failures; hand off only for a real CAPTCHA/security gate, missing material fact, or user-only action.
14. On Review, compare each section to the source profile. Confirm requisition, email, phone, education, jobs, screening answers, and resume filename; resolve every visible error.
15. For hCaptcha/CAPTCHA, email verification, identity verification, or assessments, do not bypass the gate. For CAPTCHA, apply the umbrella skill's `references/captcha-handoff-recovery.md`: distinguish dormant scripts from a genuine rendered challenge, preserve the exact draft/tab, notify Kevin immediately, and resume automatically after he completes it manually. Leave other genuine gates open and notify Kevin with the exact URL and remaining action.
16. If no manual gate remains, click Submit once. Verify Workday's application confirmation, candidate-home submitted status, or a confirmation number. Do not infer submission from navigation alone.
17. After verified confirmation, record `Submitted - Pending Response` in the tracker and send an applied Discord notification. On failure, preserve the draft and send the exact blocker.
18. Read the rendered page before interacting with stateful controls — inspect the visible label, current selection, and validation/error text before trying to change a Workday dropdown or multiselect.
19. Prefer actual option selection over typing for pickers — if the control is a dropdown, combobox, multiselect, or chip picker, select from the rendered option list rather than assuming typed text commits the value.
20. Verify picker state after every selection — confirm the visible selected chip/button text and any hidden bound value actually changed, because Workday controls can display a typed value while still treating the field as unset.
21. On stubborn forms, use OCR/visual inspection as the first debugging move, not brute-force clicking — re-read what the page is really showing before retrying.

## File Upload Pattern

Locate the correct resume input by its nearby label and accepted file types, then call `DOM.setFileInputFiles`. If Workday replaces the input after parsing, re-query the DOM before verification.

## Pitfalls

- Workday accounts are tenant-specific; an account on one employer's tenant may not exist on another.
- Resume parsing commonly corrupts dates, employer names, and education.
- Continue buttons can be enabled while hidden required fields still fail server validation.
- Conditional controls appear after earlier answers; re-inventory each step.
- Never use a stale saved answer when the live question wording differs.
- A saved draft is not a submitted application.

## Verification

- Duplicate and MAANGO policy checks passed.
- Every parsed value was compared to profile/resume.
- Each wizard step advanced without validation errors.
- The exact resume filename is displayed.
- Submission is claimed only with Workday confirmation evidence.
- Tracker and Discord message match the verified outcome.
