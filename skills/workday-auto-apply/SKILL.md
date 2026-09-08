---
name: workday-auto-apply
description: "Fill and verify Workday job application wizards."
version: 1.2.0
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
- Notifier: `~/Documents/job-agent/notifier.py`.
- **Chrome 136+ silently refuses CDP on the real default profile.** The process accepts `--remote-debugging-port`, but nothing ever listens, `DevToolsActivePort` holds a stale port, and `/json/version` returns empty. This is expected on current Chrome — it is not a misconfiguration, not proof debugging is disabled, and **never a reason to ask Kevin how to connect**. Recover it yourself with the profile-mirror procedure in `authenticated-browser-workflows` → `references/normal-chrome-routing-and-cdp.md`, which preserves his logins and leaves his normal Chrome running.
- Discover and reuse the task's approved normal-Chrome connection using `authenticated-browser-workflows` → `references/normal-chrome-routing-and-cdp.md`; never assume a port. A private Unix worker may hold the approved browser WebSocket, and Chrome UI debugging can expose that socket while `/json/list` returns 404. A fresh connection requires Kevin to approve any Chrome consent prompt.
- Primary resume is the path stored in `profile.json`.

## Executable Handler Contract

For every Workday tenant/application, load this skill and use the verified local handler before browser mutation:

- Handler: `~/Documents/job-agent/workday_handler.py`
- Tests: `~/Documents/job-agent/tests/test_workday_handler.py`
- Safe fixtures: `~/Documents/job-agent/fixtures/workday*.html`
- Multi-ATS preflight: `~/Documents/job-agent/ats_preflight.py`
- Verified CDP helpers: `scripts/workday_cdp_helpers.py` in this skill — front-bringing install, id-or-automation-id field resolution, overlay-aware clicks, exact option selection with post-scroll re-measurement, year-first date entry, and a step-change-verifying `advance()`. Prefer these over ad-hoc JS; each guard exists because the naive version failed silently on a live tenant.

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

Exit code `2` means a manual gate, parser mismatch, or resume read-back failure blocks preparation. Never reinterpret that as success. Through `terminal`, run the configured interpreter with `run_offline_tests.py tests/test_workday_handler.py -q`, then the full guarded suite after handler changes. Retain the shared browser-launch exclusions; unfiltered pytest is not authorized by an ordinary build request.

Each employer is a separate Workday account boundary. Prefer a verified existing authenticated tenant session, then any indexed tenant-specific Keychain service `hermes-job-agent-tenant-<exact-hostname>`. Otherwise create the tenant account for `kevinkpyo@gmail.com` with the account-creation value stored in macOS Keychain service `hermes-job-agent-workday-universal`, then activate/sign in and verify the exact tenant/job route. If sign-in rejects the value or the account already exists, use Forgot Password once, retrieve only the newest exact tenant reset link/code through the approved read-only Gmail flow, set New Password and Confirm Password from Keychain service `hermes-job-agent-reset-universal`, verify explicit reset success, sign in again, and save that verified current value under the exact tenant-specific service for future runs. Never copy either value into memory, skills, profile files, logs, Git, Discord, tracker data, or user-facing output. Verify Keychain records by metadata only. A standard Workday email/password login or account-creation page is not a human gate under this workflow: complete it in the same run and continue the application rather than asking Kevin to sign in. Only if the required Keychain record is actually missing/denied, or a genuine CAPTCHA, passkey, MFA approval, device-trust, identity, or security challenge appears, leave the exact tenant tab open and ask Kevin to clear that specific blocker.

Account creation lessons:

- Workday account activation and password-reset emails may have empty bodies in the simple Gmail wrapper. Search broadly by subject/sender—including employer-specific senders such as `myworkday@<employer-domain>`—then use read-only Gmail API `format=raw` MIME parsing to extract only the exact tenant activation/reset URL. Always choose the newest message: reset links can expire quickly or be invalidated by a later request. Open the newest link and complete reset, sign-in, and redirect verification without unnecessary delay.
- Activation must be verified before sign-in. A visible `Account Activated` or `Password has been reset` state is evidence; clicking alone is not.
- Some Workday submit/sign-in/reset buttons are covered by a visible `data-automation-id="click_filter"` overlay. Clicking the underlying hidden button can be a no-op. Inspect `document.elementFromPoint(...)` and invoke the visible overlay whose `aria-label` matches the intended action. Reacquire its bounding box after every scroll/rerender; stale coordinates can miss even when they were correct one call earlier. For password reset, require the visible `Password has been reset` state before attempting sign-in.
- Workday React controls can display values set through DOM mutation without committing them to application state. Use focused CDP/browser input events, then save and verify the server-rendered Review page. Date spinbuttons may rerender after each digit; refetch IDs and verify month/year after every change. For a blank MM/YYYY pair, set the year first and the month last, then re-read both values; setting the year after the month can clear the month while leaving a misleading `MM/YYYY` shell.
- Work Experience is a React field array, not a collection of independent DOM cards. Rapidly mutating several cards/fields without allowing each rerender to settle can collapse the server-saved array to one card even while the page still displays several. Change one field at a time through the native input/textarea setter plus bubbling input/change and a real focus/blur cycle, wait for rerender, reacquire the live card, and only then change the next field. After Save and Continue, verify the array on server-rendered Review or by reopening the canonical `/apply` route; an immediate Back transition can show stale/blank cards or raise a discard dialog and is not authoritative read-back.
- Workday parsing is not authoritative. Compare every parsed job title, employer, date, school, degree, GPA, skill, email, and phone to the profile/resume. Correct material field errors and delete hallucinated or duplicated records. Preserve each resume-autofilled Role Description exactly as Workday produced it—even when the first sentence lacks a bullet—and do not spend time cleaning bullets, line breaks, or wording. Change a Role Description only if the field itself blocks required validation.
- Workday can retain an older account resume while accepting a new upload. Read `profile.json -> resume.primary` at the start of every application and use its exact current path and basename; never hardcode a filename learned in an earlier session. Reject every path in `resume.do_not_use_for_applications`. If multiple attachments appear, verify the final Review filename and file size match the current primary resume before Submit.
- Workday multiselect answers are option-backed state, not free text. Typing is allowed only to filter/search. Always click the exact rendered option and verify the selected chip/button text before leaving the control.
- Generic browser `fill_input` may append to a populated React input instead of replacing it. After every write, read the actual value. For replacement, focus the live control, select all, use CDP `Input.insertText`, blur with a real Tab event, and verify the exact value before saving.
- Workday commonly omits `Data Science` from Major/Field of Study option lists. Do not search the full list or leave the control open: select the real `Other` option first; if `Other` is unavailable, select the real `Information Science` option. Verify the bound selection and continue.
- A successful tenant account creation can redirect back to Sign In while the account still requires email verification. Retrieve only the exact activation URL through read-only Gmail MIME parsing, verify activation via the `/login/ok` state, then sign in with the Keychain credential and confirm the application resumes at the intended job.
- **How Did You Hear About Us is a two-step dropdown flow:** first select the real `Social Media` option (some tenants label it `Social Networking Site`); then, when the dependent follow-up appears, select `Instagram`, with `Facebook` and `TikTok` as fallbacks. Never type `Social Media` and move on—the typed text can clear on blur while the required state remains unset.
- Preserve the parent selection before handling the dependent social-network question. Re-inventory the page after selecting the parent because Workday reveals conditional controls dynamically.
- The first fully learned tenant took longer because account creation, activation, password reset, parser repair, click-overlay discovery, and server-state corrections were being discovered. Reuse these verified procedures on later tenants: preflight account/login first, use Keychain credential, activate via read-only email link, upload only the profile's current primary resume, correct parser output using native input, handle dropdowns by real option clicks, and verify Review. Do not repeat exploratory retries already documented here.
- **Canonical-route recovery:** if the resume-start route or a long-lived React page becomes inconsistent, navigate to the authenticated canonical `/apply` route for the exact requisition. Let it render server-saved state, then resave completed steps in order. This can remove the resume-start shell, rebuild the wizard, and expose which answers were actually persisted.
- **Browser target recovery:** a Browser Use target can drift to `about:blank`, another Chrome tab, or an unrelated SSO page, and a harness daemon can time out. Preserve the Workday account/draft, use a fresh named browser session when the old daemon hangs, navigate the exact URL, and keep delayed render inspection in the same browser call so tab selection does not drift between calls.
- **Persistence over premature handoff:** repeated nudges can be appropriate when the remaining failures are recoverable UI state, delayed email, session drift, or transient Workday errors. Keep working until confirmation. Stop only for a real CAPTCHA/security gate, missing material fact, or user-only action—not because the first synthetic interaction failed.

## Procedure

1. Read the profile and verify the exact `resume.primary` file exists and is not in `resume.do_not_use_for_applications`. Do not open or query the Google Sheets tracker; use the live Workday Candidate Home/current application state for duplicate detection, unless Kevin explicitly asks for tracker synchronization.
2. Route Meta, Amazon, Apple, Netflix, Google, and Microsoft (including clear subsidiaries) to Discord with `notifier.py maango`; do not apply automatically.
3. Open the listing and verify it is active. Record company, role, location, requisition ID, salary, and tenant hostname.
4. Select the fastest truthful path. Reuse a verified tenant session first. Otherwise create/sign in as `kevinkpyo@gmail.com` using only the Keychain account-creation service `hermes-job-agent-workday-universal`. If the account already exists or sign-in rejects that value, use Forgot Password once, retrieve only the newest exact tenant reset link/code through the approved read-only Gmail workflow, set and confirm the replacement value from Keychain service `hermes-job-agent-reset-universal`, verify explicit reset success, then sign in and confirm the application resumes at the intended requisition. Never embed, print, save, or transmit either secret through skills, memory, files, logs, chat, Discord, or tracker data. CAPTCHA/passkey/device-trust gates remain human-only.
5. Work through the wizard in order: My Information, My Experience, Application Questions, Voluntary Disclosures, Review, Submit. After each Continue, verify the step changed and no validation errors remain.
6. In My Information, fill contact and address data from `profile.json`. If a required ZIP, street, state of driver's license, or other missing fact is not available, notify Kevin instead of inventing it.
7. Upload the resume using the exact Workday resume input and CDP `DOM.setFileInputFiles`. Verify the browser file object and rendered filename.
8. Workday parsing is not authoritative. Compare every parsed job title, employer, date, school, degree, GPA, skill, email, and phone to the profile/resume. Correct material field errors and delete hallucinated or duplicated records. Leave every resume-autofilled Role Description unchanged; cosmetic bullet formatting and the missing bullet on the first sentence are not errors and must not be repaired. Change a Role Description only if required validation blocks progress.
9. Do not add experience absent from Kevin's resume. Preserve present-tense jobs and accurate month/year granularity; do not fabricate exact dates when only years are known.
10. Answer conditional questions from `profile.json`: US authorization Yes, future sponsorship No, age 18+ Yes, relocation Yes, graduation Spring 2028. Re-scan after each answer because Workday may reveal new controls.
11. Optional cover letter: skip. For mandatory compensation, use the canonical approved defaults from the umbrella skill and choose a real rendered range when applicable; do not invent a salary or type into an option-backed control.
12. Voluntary disclosures: Male, Asian, not a veteran, disability Decline to answer. Complete required acknowledgments only after reading their visible text; do not opt into unrelated communications by default.
13. Use Save as Draft whenever an interruption, session warning, assessment, or unknown question appears. Workday sessions can expire in 15–30 minutes. Prefer Kevin’s approved normal Chrome profile and do not migrate a healthy live draft merely for convenience. If a Browser Use session is already carrying the authenticated draft, preserve and recover it with the canonical-route and fresh-session procedures above. Continue through recoverable UI/session failures; hand off only for a real CAPTCHA/security gate, missing material fact, or user-only action.
14. On Review, compare each section to the source profile. Confirm requisition, email, phone, education, jobs, screening answers, and resume filename; resolve every visible error.
15. For hCaptcha/CAPTCHA, email verification, identity verification, or assessments, do not bypass the gate. For CAPTCHA, apply the umbrella skill's `references/captcha-handoff-recovery.md`: distinguish dormant scripts from a genuine rendered challenge, preserve the exact draft/tab, notify Kevin immediately, and resume automatically after he completes it manually. Leave other genuine gates open and notify Kevin with the exact URL and remaining action.
16. If no manual gate remains, click Submit once. Verify Workday's application confirmation, candidate-home submitted status, or a confirmation number. Do not infer submission from navigation alone.
17. After verified confirmation, send an applied Discord notification. Do not open or update the Google Sheets tracker by default; do that only when Kevin explicitly requests tracker synchronization for the specific application. On failure, preserve the draft and send the exact blocker.
18. Read the rendered page before interacting with stateful controls — inspect the visible label, current selection, and validation/error text before trying to change a Workday dropdown or multiselect.
19. Prefer actual option selection over typing for pickers — if the control is a dropdown, combobox, multiselect, or chip picker, select from the rendered option list rather than assuming typed text commits the value.
20. Verify picker state after every selection — confirm the visible selected chip/button text and any hidden bound value actually changed, because Workday controls can display a typed value while still treating the field as unset.
21. On stubborn forms, use OCR/visual inspection as the first debugging move, not brute-force clicking — re-read what the page is really showing before retrying.

## Control identity and option-selection pitfalls

Learned on the Marvell tenant; these cost the most retries and apply to every Workday tenant.

- **Bring the tab to front before any input.** Synthetic mouse/key events are discarded when `document.visibilityState` is `hidden` — correct coordinates, correct element, no error, no effect. Call `Page.bringToFront` and confirm visibility before concluding a selector is wrong.
- **Many inputs are keyed by `id`, not `data-automation-id`** (`name--legalName--firstName`, `address--postalCode`, `education-42--degree`, `workExperience-49--jobTitle`). Resolve a field by `id` first, then `data-automation-id`, then a raw selector. The numeric card index is assigned per render — re-read it after every add/rerender instead of reusing a remembered value.
- **Ids beginning with a digit** (`64cbff5f...-disabilityStatus`) are invalid in `#id` CSS selectors and throw. Use `[id="..."]`.
- **Never fuzzy-match an option label.** A fuzzy `Bachelor` match selected `Bachelor of Arts (BA)` for a B.S. candidate. Enumerate the rendered options, match exactly against an ordered candidate list, then verify the bound text equals the intended label and correct it in place when it does not.
- **Re-measure after `scrollIntoView`.** Capture the option's bounding box only once the list has settled; a coordinate taken before the scroll completes lands on the wrong row or on nothing, leaving the field silently at `0 items selected` while the click appears to succeed.
- **A saved work-experience card can vanish entirely.** Filling the React field array too quickly persists nothing: the step advances cleanly, but Review renders `Professional Experience — No Response`. Always confirm each added card on Review; if it is missing, go Back, re-add it writing one field at a time with a settle pause between writes, and re-verify on Review before Submit.
- Marvell-shaped tenants use a 6-step wizard (My Information → My Experience → Application Questions → Voluntary Disclosures → Self Identify → Review) plus a `Create Account/Sign In` step that reports as step 1 of 7 before login.
- **Never interpolate a credential into a JavaScript expression.** Building `window.__wd.setText('password', '<secret>')` breaks when the secret contains a quote or backslash: the evaluate call returns `{'__error__': 'Uncaught'}`, the field stays empty, and the submit silently does nothing. Click the field and deliver the value with trusted `Input.insertText`, then verify by **length only** (`pwLen`), never by echoing the value.
- **Option lists are tenant-specific; enumerate before selecting.** Degree wording varies (Marvell: `Bachelor of Science (BS)`; Medtronic: plain `Bachelors` with no BA/BS split). Veteran status varies (`I am not a protected veteran` vs `I AM NOT A VETERAN`). Ethnicity varies (`Asian (Not Hispanic or Latino) (United States of America)` vs `Asian (United States of America)`, sometimes with a separate Hispanic/Latino Yes/No question). Always read the rendered options and match exactly.
- **A school search can return a truncated, alphabetically-cut list.** Medtronic's directory returned 24 entries for `University of California` and stopped at `-Merced`, so San Diego was never visible. When the expected campus is absent from a truncated list, search a longer exact string (`University of California-San Diego`) instead of concluding the school is missing or falling back to `Other`.
- **Close an open picker before reading another control's options.** A still-open dropdown makes `[role="option"]` return the *previous* field's list, which looks like the new control having absurd options (a degree list showing university names). Dispatch Escape and confirm the option count dropped before opening the next control.
- Returning a DOM element from `Runtime.evaluate` with `returnByValue` raises `Object reference chain is too long`. Return a primitive (`?true:false`, an id string, a count) instead.

## Public snapshots without controls

Read `job-application-automation` → `references/workday-empty-snapshots.md` when a public shell has bootstrap/JobPosting metadata but no inventoried application controls. Unrecognized zero-control snapshots are `unknown`, not applications or closed jobs; preparation stays blocked. Existing listing/start/confirmation precedence and all gate evidence remain. No static snapshot establishes connected Workday support, saved Review, or submission authority.

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

- MAANGO policy checks passed; duplicate detection used only the live portal/current task and did not open Sheets.
- Every parsed value was compared to profile/resume.
- Each wizard step advanced without validation errors.
- The exact resume filename is displayed.
- Submission is claimed only with Workday confirmation evidence.
- Discord message matches the verified outcome. Tracker verification is required only when Kevin explicitly requested tracker synchronization for this application.
