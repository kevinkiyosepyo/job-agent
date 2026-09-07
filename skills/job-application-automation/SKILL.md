---
name: job-application-automation
description: "Use when auto-applying to jobs via browser ATS forms."
version: 2.2.4
author: Kevin Pyo, Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [jobs, automation, browser, ats, applications, cdp]
    related_skills:
      - job-scanner
      - ats-form-filling
      - greenhouse-auto-apply
      - workday-auto-apply
      - workday-ats-filling
      - lever-auto-apply
      - oracle-auto-apply
      - custom-job-application-forms
---

# Job Application Automation

Umbrella skill for Kevin Pyo's end-to-end job discovery, preparation, submission, tracking, and notification pipeline. Load this skill first for job applications, then load the ATS-specific child selected by the router below.

## When to Use

- Kevin asks to find, evaluate, prepare, test, or submit job applications.
- A scheduled job scan discovers a verified lead.
- An ATS form needs resume upload, screening answers, account handling, Review verification, or submission reconciliation.

## Child Skill Router

| Surface | Detect | Load next |
|---|---|---|
| Discovery and dedup | scan/search request | `job-scanner` |
| Any complex ATS control | dropdown/chip/date/file input | `ats-form-filling` |
| School/university picker | directory, autocomplete, institution field | `education-school-picker` |
| Greenhouse | `greenhouse.io`, `job-boards.greenhouse.io` | `greenhouse-auto-apply` |
| Workday | `myworkdayjobs.com`, `myworkdaysite.com` | `workday-auto-apply` and `workday-ats-filling` |
| Lever | `jobs.lever.co`, `lever.co` | `lever-auto-apply` |
| Oracle Recruiting | `oraclecloud.com`, Oracle Candidate Experience | `oracle-auto-apply` |
| Ashby | `jobs.ashbyhq.com` | `custom-job-application-forms` plus this skill's `references/ashby-application-forms.md` before any form interaction |
| Custom/embedded form | no supported ATS contract | `custom-job-application-forms` |

These are persistent sibling skills linked to this umbrella, not files embedded inside one SKILL.md. In every chat under the same Hermes profile, the skills remain available. The umbrella's job is to enforce shared policy and route to the specialized procedure.

## Canonical Sources

1. `~/Documents/job-agent/profile.json`
2. Primary resume: always read `profile.json -> resume.primary`; never hardcode a previously used filename. The current approved file is `/Users/kevinpoopz/Downloads/Resume 2027 SWE.pdf`.
3. Application knowledge Google Doc ID: `1zqr26fQKzwAgPMbdyYPoTDAcLKjGoQ4PKxMLug4hr-k`
4. Resume wins conflicts unless Kevin explicitly confirms a newer fact.

The application knowledge Doc can contain plaintext credentials mixed with historical application text. Never return or log its entire contents. Filter locally/in-page to the specific non-secret question and a narrow answer window before tool output, and redact credential-bearing lines. Credential use belongs to the approved Keychain workflow, not values found in this Doc. Historical autofill errors are not confirmed facts.

Never use a path listed in `resume.do_not_use_for_applications`. Require the final Review page to display the exact basename from `resume.primary`.

## Global Pipeline

1. Verify the official listing is active and extract company, role, location, requisition, compensation, and ATS. If extracted qualification headings lack their bullet lists or the page is only a shell, read `references/public-qualification-source-completeness.md`; recover the full official body before eligibility filtering. Neither API/Markdown retrieval nor sparse HTML proves rendered application state.
2. Do not open or query the Google Sheets tracker for duplicate checking. Avoid duplicates using the live candidate portal/current application state and the exact URL already present in the current task; inspect the tracker only when Kevin explicitly requests tracker synchronization.
3. Enforce MAANGO approval before mutation.
4. Load the ATS child skill and its executable handler/preflight.
5. Inventory the entire form—not only the currently highlighted step—including current values, selected chips, dynamic control IDs, uploads, conditional sections, and manual gates. Run browser-native validity checks and enumerate invalid controls before advancing. Preserve exact correct values, replace incorrect values atomically, and never assume a control's index remains stable after parsing or rerendering.
6. Use the tenant account/identity flow defined by the child and `secure-login-and-2fa`. Prefer a verified existing authenticated session, then any indexed tenant-specific Keychain service for the exact hostname. Otherwise create the account for `kevinkpyo@gmail.com` with Keychain service `hermes-job-agent-universal` (Workday alias `hermes-job-agent-workday-universal`), then sign in and verify the exact tenant/job route. If sign-in rejects the value or the account already exists, use Forgot Password once, read only the newest exact tenant reset link/code from Kevin's authorized Gmail, reset using Keychain service `hermes-job-agent-reset-universal`, verify explicit reset success, sign in, and save the verified current value under `hermes-job-agent-tenant-<exact-hostname>` for future runs. Never guess a service name or read/store plaintext in Markdown, memory, Discord, tracker rows, logs, or Git. An ordinary email/password login or account-creation page is not a human/security gate under this authorized protocol: do not hand it off to Kevin and do not stop after promising to follow the protocol—execute it in the same run and continue the application. CAPTCHA, assessments, passkeys, identity verification, MFA approval, and device-security prompts remain human gates.
7. Upload only `profile.json -> resume.primary`; verify browser file object, rendered upload success, and final Review filename.
8. Fill truthful facts from profile/resume. Unknown material facts fail closed. Distinguish explicit required qualifications from preferred/bonus qualifications: a missing bonus qualification is not a blocker and must not be treated as a required application question.
9. Treat dropdowns, multiselects, chips, salary ranges, school, country, source, and dates as stateful option-backed controls on every ATS. Use the routed child skill's exact control strategy, select one real rendered option, and verify the bound value. Never type-only, reuse a stale index, or infer that one ATS implementation applies to another. For school/university controls, route to `education-school-picker`.
10. Save each step and read back server-rendered values. DOM-visible text alone is not proof.
11. Persist through recoverable ATS failures: stale React state, disabled buttons, expired sessions, delayed email, target drift, and transient "Something went wrong" pages are debugging signals—not automatic handoff points. Reacquire the live control, reopen the canonical application route, or resume the server-side draft. For CAPTCHA indicators, follow `references/captcha-handoff-recovery.md`: automatically ignore dormant scripts, hidden containers, and inactive integrations; continue through ordinary ATS controls without asking Kevin; and hand off only when a genuine rendered CAPTCHA/“I'm not a robot” checkbox, managed challenge, CAPTCHA-owned Verify action, or required challenge token actually blocks progress. Preserve the exact tab during that human/security gate, then detect clearance and resume automatically without requiring Kevin to repeat application instructions. Hand off only for a genuine human/security gate or an unavailable material fact.
12. Review every section against the profile/resume and resolve all validation errors.
13. Click Submit once only when authorized, complete, and free of manual gates.
14. Require explicit confirmation page/text, reference number, or candidate-home application entry.
15. Do not update, open, or reconcile the Google Sheets job tracker by default. Workday/ATS confirmation plus the Discord result notification are sufficient. Only write or read back the tracker when Kevin explicitly asks for tracker synchronization for that specific application.
16. Send the Discord result and read back the exact delivered message.

## Kevin Defaults

- Work authorization: Yes
- Sponsorship: No
- Age 18+: Yes
- Relocation: Yes
- Education: UC San Diego, B.S. Data Science, Sep 2024-May 2028, cumulative GPA **3.236** (explicitly confirmed for submission). Use the same accurate GPA whether or not a transcript upload is requested; re-confirm any future conflict rather than reviving older 3.8 defaults.
- Permanent application address: Fairfax, Virginia profile address
- Driver's-license answer: California
- Outside business activities: No
- Honeywell/Oracle baseline: No restrictive covenant; never Deloitte employee; no Honeywell relationship; never Honeywell employee; no U.S.-government procurement role involving Honeywell; never suspended/debarred from federal contracts.
- Optional cover letter: skip
- Gender: Male
- Race/ethnicity: Asian; Hispanic/Latino: No
- Veteran: Not a protected veteran
- Disability: Decline to answer
- Compensation when mandatory: $20/hour or $20k annual, choosing a real dropdown range when applicable
- Soonest available starting date: **September 2026**
- Winter/full-time internships are acceptable; do not assume Kevin wants summer-only opportunities or reject a role solely because its dates overlap school terms. Use his explicit approval for the role's dates when answering availability questions; do not invent a school-schedule conflict.

### Referral Source: Mandatory Two-Step Selection

1. Open the real parent dropdown.
2. Select the rendered `Social Media` option; some tenants call it `Social Networking Site`.
3. Re-inventory the form for the dependent child question.
4. Select `Instagram`; use `Facebook`, then `TikTok`, only as fallbacks.
5. Verify both saved values on the step or Review page.

Typing `Social Media` without selecting the option is never valid completion.

## Hard Safety Rules

- Never claim Applied from a click, spinner, disabled button, sent request, or navigation alone.
- Never bypass CAPTCHA, assessments, email/identity verification, or account security. Use `references/captcha-handoff-recovery.md` to distinguish dormant code from a genuine rendered gate, preserve the exact tab, notify Kevin, and resume after manual completion.
- Never fabricate dates, GPA, experience, certifications, salary, legal answers, or clearances.
- Never submit MAANGO without approval.
- Never send/delete/archive/modify email; verification-link reading is read-only.
- Never store raw credentials in memory, skills, profile, Git, logs, Discord, or user-facing output. Workday credential is referenced through macOS Keychain by its child skill.
- Never trust ATS resume parsing or DOM-only edits; final Review is authoritative.
- Never upload a resume based on recency guessing. Use exact profile path and prohibited-file list.

## Shared Executable Components

Repository: `~/Documents/job-agent`

- `scanner.py`, `sources.py` — discovery/classification
- `orchestrator.py`, `production_run.py` — safe orchestration
- `app_queue.py`, `queue_worker.py`, `execution_journal.py` — durable state
- `question_engine.py` — profile/knowledge answers
- `greenhouse_handler.py`, `workday_handler.py`, `lever_handler.py`, `oracle_handler.py` — ATS inspectors; Greenhouse emits prefilled-control and dynamic-education hints
- `browser_actions.py`, `mutable_cdp_page_adapter.py` — verified native-setter text replacement and exact React Select option binding
- `ats_preflight.py`, `prepare_job.py`, `ats_registry.py` — routing/preflight
- `submission_artifacts.py` — sanitized confirmation evidence
- `mutable_cdp_page_adapter.py`, `prepare_live_job.py` — exact-target bounded CDP preparation with sanitized Review evidence
- `review_reconciler.py` — authoritative server-rendered Review comparison and evidence hash
- `submission_authorization.py` — expiring single-use authorization bound to exact job/target/Review state
- `one_shot_submit.py`, `page_recovery.py` — one exact Submit with intent journaling and confirmation inspection without replay
- `confirmation_reconciliation.py` — learned-ATS confirmation plus Candidate Home/application-list reconciliation
- `post_submit_transaction.py` — resumable portal → tracker/read-back → Discord/read-back transaction
- `tenant_field_maps.py` — versioned learned controls and conditional steps for Njoyn, Workday, Greenhouse, Lever, and Oracle
- `production_operator.py` — sanitized local end-to-end proof and read-only final audit
- `tracker.py`, `notifier.py` — verified external reconciliation

### Unattended-run readiness

Installed/available skill status and passing fixture tests are not proof that applications will run unattended. Before claiming overnight readiness:

1. Read `references/hourly-new-job-pacing.md`. Inspect the actual application schedule/service, enabled state, resolved cron model/provider, delivery target, and recent run outcomes. A monitor, completed engineering sprint, or scheduler `ok` result is not a verified application.
2. Verify the approved normal-Chrome transport actually used by the executor, not merely an HTTP health endpoint. Check the configured interpreter/dependencies and host power/session prerequisites without opening another browser or approving security prompts.
3. Reconcile the installed umbrella, linked references, repo-vendored skills, canonical profile, and executable behavior. No-Sheets-by-default and the exact current resume must hold in code as well as prose. Do not run a legacy tracker-dependent command to work around a policy conflict.
4. Require a passing connected prepare → supported Review evidence → authorization → one-shot submit → ATS confirmation path for each enabled form family. Label isolated adapters, fixture-only flows, and verification-only bridges accurately. Review must compare facts independently to canonical profile/user approval, bind actual normalized answer values and resume bytes in a private content commitment, and require explicit evidence provenance. Equality to an agent-created answer file, a hash of only `verified` booleans, or a filename alone is not sufficient evidence. Never use missing Review source metadata as a more permissive fallback.
5. Preserve one-shot uncertainty across restarts and concurrent workers. Park genuine human-gated candidates without blocking unrelated eligible candidates before submit intent; do not replay or advance to a second application in a run after uncertain submit intent.
6. Report confirmed submission, notification delivery, and optional tracker sync as separate states. Retrying notification must never repeat submission. Health reporting must detect dependency failures and distinguish zero eligible leads from an execution failure.

### Production operator status

For the guarded unattended controller, also read [`references/unattended-controller.md`](references/unattended-controller.md) and the repository's `autonomous_operation.md`. Scope, legacy-history reconciliation, verified live capability, and explicit service enablement are separate from passing unit tests. The manual `production_operator.py live` interface below remains available; do not confuse a controller's policy-scoped authorization with an unbounded permission to apply anywhere.

The repository now exposes a unified, guarded `production_operator.py live` command family. Before using any live subcommand, read [`references/unified-live-production-cli.md`](references/unified-live-production-cli.md) completely and follow its command order, approval boundaries, no-replay recovery, health checks, and release-audit contract.

The build/release audit is deliberately non-authorizing: a passing result is only `ready_for_manual_live_authorization_review` and always reports `real_live_enabled: false`, `commit_external_enabled: false`, and `real_application_authorized: false`. A real run still requires a separately enabled `production_live` manifest plus every stage-specific gate at the moment of use. Never infer production authority from this skill, a manifest value, an earlier Review, or a passing local test.

Run the older sanitized proof only as a local regression check:

```bash
python production_operator.py local-demo \
  --resume runtime/sanitized-demo/Resume.pdf \
  --runtime-dir runtime/sanitized-demo/run \
  --output runtime/sanitized-demo/operator-report.json \
  --approve-sanitized-submit
python production_operator.py audit \
  --report runtime/sanitized-demo/operator-report.json
```

A passing report does not authorize a real application. Do not manufacture live evidence from the local fixture or substitute child-skill browser actions for the unified CLI's exact-target and single-use gates.

After code changes, inspect test side effects before running the suite. Prefer the repository's `python run_offline_tests.py` when present. Otherwise exclude `tests/test_local_cdp_operator.py`, `tests/test_production_operator_live_chrome.py`, and `tests/test_production_operator.py::test_cli_runs_and_audits_full_sanitized_learned_ats_operator_under_targets`: these can launch isolated Chrome, which is not authorized by ordinary application/build requests. Report excluded browser coverage explicitly; fixture-only success is not live readiness.

## LandedHQ Reconciliation

After verified submissions, synchronize `https://www.landedhq.dev/dashboard/applying/applications` when Kevin requests it:

1. Read the live Google Sheet through authenticated Sheets API and include only exact `Submitted - Pending Response` rows. Exclude discovered leads, prepared forms, drafts, blockers, and unconfirmed applications.
2. Dedupe against LandedHQ My Applications by normalized company, role, and listing URL. Preserve existing entries and statuses.
3. For tracker rows where a job title was mistakenly stored in Company Name (for example American Express campus rows), use the actual employer as Company and preserve the full original title as Role.
4. Use Add Application fields `#company`, `#role`, and optional `#applyUrl`. LandedHQ is React-controlled: use browser-native input events, select the real category option, read back values, and submit the form only when enabled.
5. A successful custom import resets the form, displays `Added <role> at <company>`, increments Total Applications, and creates an `Applied` card. Verify every expected company/role pair in the rendered My Applications page and verify final `N of N tracked` totals.
6. The manual-add form has no historical submission-date field; imported older applications are recorded as added on the import day. Do not imply LandedHQ preserved their original tracker dates.

## Verification Contract

A completed application must have all of:

- Exact official company/role/requisition
- Final Review values matching profile/resume
- Exact current resume basename from `profile.json -> resume.primary` displayed
- No unresolved validation/manual gate
- Explicit confirmation or Candidate Home entry
- If Kevin explicitly requested tracker synchronization for this application, the tracker status `Submitted - Pending Response` was verified by exact read-back; otherwise tracker work is intentionally omitted.
- Discord success message verified by Discord read-back

If any element is missing, report the exact pending/failed state instead of Applied.

## References

- `references/kevin-profile.md`
- `references/screening-answers.md`
- `references/kevin-application-writing-voice.md`
- `references/click-type-select.md`
- `references/captcha-handoff-recovery.md`
- `references/ats-and-pipeline.md`
- `references/ashby-public-discovery.md` — explicit public discovery and non-live saved-snapshot replay; not connected application support.
- `references/greenhouse-fieldset-inspection.md` — static checkbox questions and exact options; no saved-state authority.
- `references/lever-location-picker.md` — paired location control kind, not selected location or connected support.
