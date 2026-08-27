1|---
2|name: job-application-automation
3|description: "Use when auto-applying to jobs via browser ATS forms."
4|version: 2.1.0
5|author: Kevin Pyo, Hermes Agent
6|license: MIT
7|platforms: [macos]
8|metadata:
9|  hermes:
10|    tags: [jobs, automation, browser, ats, applications, cdp]
11|    related_skills:
12|      - job-scanner
13|      - ats-form-filling
14|      - greenhouse-auto-apply
15|      - workday-auto-apply
16|      - workday-ats-filling
17|      - lever-auto-apply
18|      - oracle-auto-apply
19|      - custom-job-application-forms
20|---
21|
22|# Job Application Automation
23|
24|Umbrella skill for Kevin Pyo's end-to-end job discovery, preparation, submission, tracking, and notification pipeline. Load this skill first for job applications, then load the ATS-specific child selected by the router below.
25|
26|## When to Use
27|
28|- Kevin asks to find, evaluate, prepare, test, or submit job applications.
29|- A scheduled job scan discovers a verified lead.
30|- An ATS form needs resume upload, screening answers, account handling, Review verification, or submission reconciliation.
31|
32|## Child Skill Router
33|
34|| Surface | Detect | Load next |
35||---|---|---|
36|| Discovery and dedup | scan/search request | `job-scanner` |
37|| Any complex ATS control | dropdown/chip/date/file input | `ats-form-filling` |
38|| Greenhouse | `greenhouse.io`, `job-boards.greenhouse.io` | `greenhouse-auto-apply` |
39|| Workday | `myworkdayjobs.com`, `myworkdaysite.com` | `workday-auto-apply` and `workday-ats-filling` |
40|| Lever | `jobs.lever.co`, `lever.co` | `lever-auto-apply` |
41|| Oracle Recruiting | `oraclecloud.com`, Oracle Candidate Experience | `oracle-auto-apply` |
42|| Custom/embedded form | no supported ATS contract | `custom-job-application-forms` |
43|
44|These are persistent sibling skills linked to this umbrella, not files embedded inside one SKILL.md. In every chat under the same Hermes profile, the skills remain available. The umbrella's job is to enforce shared policy and route to the specialized procedure.
45|
46|## Canonical Sources
47|
48|1. `~/Documents/job-agent/profile.json`
49|2. Primary resume: always read `profile.json -> resume.primary`; never hardcode a previously used filename. The current approved file is `/Users/kevinpoopz/Downloads/Resume 2027 SWE.pdf`.
50|3. Application knowledge Google Doc ID: `1zqr26fQKzwAgPMbdyYPoTDAcLKjGoQ4PKxMLug4hr-k`
51|4. Resume wins conflicts unless Kevin explicitly confirms a newer fact.
52|
53|Never use a path listed in `resume.do_not_use_for_applications`. Require the final Review page to display the exact basename from `resume.primary`.
54|
55|## Global Pipeline
56|
57|1. Verify the official listing is active and extract company, role, location, requisition, compensation, and ATS.
58|2. Check the live tracker for duplicate URL and normalized company/role.
59|3. Enforce MAANGO approval before mutation.
60|4. Load the ATS child skill and its executable handler/preflight.
61|5. Inventory all fields and manual gates before filling.
62|6. Use the tenant account/identity flow defined by the child. Never guess a service name or read a password from Markdown. Resolve the credential through the secret-free private index and retrieve it only from macOS Keychain inside the process typing the authorized form. For Workday, use service `hermes-job-agent-workday-universal`, account `kevinkpyo@gmail.com`. Handle authorized activation/OTP through the `secure-login-and-2fa` skill, but never bypass CAPTCHA, assessments, passkeys, or device-security prompts.
63|7. Upload only `profile.json -> resume.primary`; verify browser file object, rendered upload success, and final Review filename.
64|8. Fill truthful facts from profile/resume. Unknown material facts fail closed.
65|9. Treat dropdowns, multiselects, chips, salary ranges, school, country, source, and dates as stateful option-backed controls. Select real rendered options and verify bound state.
66|10. Save each step and read back server-rendered values. DOM-visible text alone is not proof.
67|11. Persist through recoverable ATS failures: stale React state, disabled buttons, expired sessions, delayed email, target drift, and transient "Something went wrong" pages are debugging signals—not automatic handoff points. Reacquire the live control, reopen the canonical application route, or resume the server-side draft. Hand off only for a genuine human/security gate or an unavailable material fact.
68|12. Review every section against the profile/resume and resolve all validation errors.
69|13. Click Submit once only when authorized, complete, and free of manual gates.
70|14. Require explicit confirmation page/text, reference number, or candidate-home application entry.
71|15. Append the eight-column tracker row and verify it through authenticated Sheets API read-back.
72|16. Send the Discord result and read back the exact delivered message.
73|
74|## Kevin Defaults
75|
76|- Work authorization: Yes
*** Sponsorship: No
78|- Age 18+: Yes
79|- Relocation: Yes
80|- Education: UC San Diego, B.S. Data Science, Sep 2024-May 2028, GPA 3.8
81|- Permanent application address: Fairfax, Virginia profile address
82|- Driver's-license answer: California
83|- Outside business activities: No
84|- Honeywell/Oracle baseline: No restrictive covenant; never Deloitte employee; no Honeywell relationship; never Honeywell employee; no U.S.-government procurement role involving Honeywell; never suspended/debarred from federal contracts.
85|- Optional cover letter: skip
86|- Gender: Male
87|- Race/ethnicity: Asian; Hispanic/Latino: No
88|- Veteran: Not a protected veteran
89|- Disability: Decline to answer
90|- Compensation when mandatory: $20/hour or $20k annual, choosing a real dropdown range when applicable
91|
92|### Referral Source: Mandatory Two-Step Selection
93|
94|1. Open the real parent dropdown.
95|2. Select the rendered `Social Media` option; some tenants call it `Social Networking Site`.
96|3. Re-inventory the form for the dependent child question.
97|4. Select `Instagram`; use `Facebook`, then `TikTok`, only as fallbacks.
98|5. Verify both saved values on the step or Review page.
99|
100|Typing `Social Media` without selecting the option is never valid completion.
101|
102|## Hard Safety Rules
103|
104|- Never claim Applied from a click, spinner, disabled button, sent request, or navigation alone.
105|- Never bypass CAPTCHA, assessments, email/identity verification, or account security.
106|- Never fabricate dates, GPA, experience, certifications, salary, legal answers, or clearances.
107|- Never submit MAANGO without approval.
108|- Never send/delete/archive/modify email; verification-link reading is read-only.
109|- Never store raw credentials in memory, skills, profile, Git, logs, Discord, or user-facing output. Workday credential is referenced through macOS Keychain by its child skill.
110|- Never trust ATS resume parsing or DOM-only edits; final Review is authoritative.
111|- Never upload a resume based on recency guessing. Use exact profile path and prohibited-file list.
112|
113|## Shared Executable Components
114|
115|Repository: `~/Documents/job-agent`
116|
117|- `scanner.py`, `sources.py` — discovery/classification
118|- `orchestrator.py`, `production_run.py` — safe orchestration
119|- `app_queue.py`, `queue_worker.py`, `execution_journal.py` — durable state
120|- `question_engine.py` — profile/knowledge answers
121|- `greenhouse_handler.py`, `workday_handler.py`, `lever_handler.py`, `oracle_handler.py` — ATS inspectors
122|- `ats_preflight.py`, `prepare_job.py`, `ats_registry.py` — routing/preflight
123|- `submission_artifacts.py` — sanitized confirmation evidence
124|- `mutable_cdp_page_adapter.py`, `prepare_live_job.py` — exact-target bounded CDP preparation with sanitized Review evidence
125|- `review_reconciler.py` — authoritative server-rendered Review comparison and evidence hash
126|- `submission_authorization.py` — expiring single-use authorization bound to exact job/target/Review state
127|- `one_shot_submit.py`, `page_recovery.py` — one exact Submit with intent journaling and confirmation inspection without replay
128|- `confirmation_reconciliation.py` — learned-ATS confirmation plus Candidate Home/application-list reconciliation
129|- `post_submit_transaction.py` — resumable portal → tracker/read-back → Discord/read-back transaction
130|- `tenant_field_maps.py` — versioned learned controls and conditional steps for Njoyn, Workday, Greenhouse, Lever, and Oracle
131|- `production_operator.py` — sanitized local end-to-end proof and read-only final audit
132|- `tracker.py`, `notifier.py` — verified external reconciliation
133|
134|### Production operator status
135|
136|The repository now exposes a unified, guarded `production_operator.py live` command family. Before using any live subcommand, read [`references/unified-live-production-cli.md`](references/unified-live-production-cli.md) completely and follow its command order, approval boundaries, no-replay recovery, health checks, and release-audit contract.
137|
138|The build/release audit is deliberately non-authorizing: a passing result is only `ready_for_manual_live_authorization_review` and always reports `real_live_enabled: false`, `commit_external_enabled: false`, and `real_application_authorized: false`. A real run still requires a separately enabled `production_live` manifest plus every stage-specific gate at the moment of use. Never infer production authority from this skill, a manifest value, an earlier Review, or a passing local test.
139|
140|Run the older sanitized proof only as a local regression check:
141|
142|```bash
143|python production_operator.py local-demo \
144|  --resume runtime/sanitized-demo/Resume.pdf \
145|  --runtime-dir runtime/sanitized-demo/run \
146|  --output runtime/sanitized-demo/operator-report.json \
147|  --approve-sanitized-submit
148|python production_operator.py audit \
149|  --report runtime/sanitized-demo/operator-report.json
150|```
151|
152|A passing report does not authorize a real application. Do not manufacture live evidence from the local fixture or substitute child-skill browser actions for the unified CLI's exact-target and single-use gates.
153|
154|Run `python -m pytest tests -q` after code changes.
155|
156|## LandedHQ Reconciliation
157|
158|After verified submissions, synchronize `https://www.landedhq.dev/dashboard/applying/applications` when Kevin requests it:
159|
160|1. Read the live Google Sheet through authenticated Sheets API and include only exact `Submitted - Pending Response` rows. Exclude discovered leads, prepared forms, drafts, blockers, and unconfirmed applications.
161|2. Dedupe against LandedHQ My Applications by normalized company, role, and listing URL. Preserve existing entries and statuses.
162|3. For tracker rows where a job title was mistakenly stored in Company Name (for example American Express campus rows), use the actual employer as Company and preserve the full original title as Role.
163|4. Use Add Application fields `#company`, `#role`, and optional `#applyUrl`. LandedHQ is React-controlled: use browser-native input events, select the real category option, read back values, and submit the form only when enabled.
164|5. A successful custom import resets the form, displays `Added <role> at <company>`, increments Total Applications, and creates an `Applied` card. Verify every expected company/role pair in the rendered My Applications page and verify final `N of N tracked` totals.
165|6. The manual-add form has no historical submission-date field; imported older applications are recorded as added on the import day. Do not imply LandedHQ preserved their original tracker dates.
166|
167|## Verification Contract
168|
169|A completed application must have all of:
170|
171|- Exact official company/role/requisition
172|- Final Review values matching profile/resume
173|- Required `Resume.pdf` displayed
174|- No unresolved validation/manual gate
175|- Explicit confirmation or Candidate Home entry
176|- Tracker status `Submitted - Pending Response` verified by Sheets API
177|- Discord success message verified by Discord read-back
178|
179|If any element is missing, report the exact pending/failed state instead of Applied.
180|
181|## References
182|
183|- `references/kevin-profile.md`
184|- `references/screening-answers.md`
185|- `references/click-type-select.md`
186|- `references/ats-and-pipeline.md`
187|