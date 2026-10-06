# Succesful apps

A running record of real, confirmed job applications completed by the agent: what happened end to end, where the flow tripped up, what resolved it, and what proved the employer received the application.

**Successful means submitted and confirmed by the employer's application system.** It does not mean an interview, offer, or acceptance. A filled form, uploaded resume, Submit click, or notification alone is not a successful application.

This log starts with the verified Mindex run below. It is not a complete historical application count. Add future entries only after checking their own confirmation evidence.

## Confirmed applications

| Application date | Employer | Role | ATS | Requisition | Result |
| --- | --- | --- | --- | --- | --- |
| October 3, 2026 (PDT) | Mindex | Software Engineer Co-Op - On-site | Workable | `84B10DB922` | Application and optional EEO survey confirmed submitted |
| October 3, 2026 (PDT) | Meta | Data Engineer Intern, Product Analytics (Summer 2027) | Meta Careers | `1373603594867455` | Applied status verified; all three follow-up items completed |
| October 5, 2026 (PDT) | Epic Games | Backend Services Programmer Intern | Greenhouse | `R27435` / `6183293004` | Exact-job confirmation and receipt text verified |
| October 5, 2026 (PDT) | Epic Games | Data Science Intern | Greenhouse | `R27453` / `6202675004` | Exact-job confirmation and receipt text verified |
| October 5, 2026 (PDT) | Epic Games | Technical Product Management Intern | Greenhouse | `R27432` / `6178818004` | Exact-job confirmation and receipt text verified |

---

## Mindex — Software Engineer Co-Op - On-site

### Job and execution context

- **Official posting:** <https://apply.workable.com/mindex/j/84B10DB922/>
- **Location:** Rochester, New York, United States.
- **Term:** January through August 2027, a full double-block co-op.
- **Work arrangement:** At least three on-site days per week; five preferred.
- **Posted compensation:** $22/hour.
- **Submission date:** October 3, 2026, at approximately 8:12 p.m. PDT (October 4 in UTC).
- **Interaction mode:** User-requested, visible browser operation. The attempt began in the Hermes browser pane and finished in the existing normal-Chrome application tab.
- **Who completed the application:** The agent entered the application data, uploaded the resume, answered the screening questions, and clicked Submit. The user did not have to select the resume or submit the form manually.

This was a supervised session with interruptions during browser troubleshooting, not an uninterrupted scheduled run. The successful route was exact-tab Chrome DevTools Protocol (CDP) control. It does **not** establish that the repository's scheduled controller has connected end-to-end Workable support.

### End-to-end flow

1. **Read the official job requirements.** Recovered the complete rendered posting after ordinary web extraction returned only a short metadata description. Checked the location, co-op dates, on-site requirement, compensation, and work-authorization conditions against the applicant's saved facts and preferences.
2. **Check for a prior submission.** Inspected the local application ledger and relevant Chrome history. The history contained a visit to this application, but neither source showed a confirmed prior submission for this requisition. No prior confirmation was treated as new work.
3. **Inspect the whole form.** Identified required contact and location fields, the resume upload, compensation, five Yes/No screening questions, employee referral, and posting source. Optional education, experience, summary, photo, and cover-letter sections were not invented or populated merely to make the form look complete; the resume supplied the applicant's background.
4. **Recover visible browser control.** After the Hermes file picker stalled, attached to the exact existing Mindex tab in normal Chrome. Activated that target and verified that it was visible before continuing screen input. No replacement background Chrome instance was needed.
5. **Upload the canonical resume.** Resolved the current resume from the private applicant profile and attached it through the observed resume file input with `DOM.setFileInputFiles`. Verified both the browser file object and the displayed resume filename after upload.
6. **Fill and bind the answers.** Entered contact details and the truthful location from the saved profile; used the posting's $22 hourly rate and Simplify as the observed source. Answered the screening questions from saved applicant facts and preferences, without inventing qualifications or changing the applicant's location to Rochester.
7. **Review before submission.** Read back contact fields, compensation, referral/source, all five selected screening answers, and the exact attached resume. Compared them with the intended profile-backed answers. The form passed native validity checks and showed no visible validation alerts or unresolved challenge.
8. **Submit once.** Recorded a task-local submission intent and dispatched one application Submit action. Did not infer success from the click or retry the application submission.
9. **Confirm employer acceptance.** Observed the exact application-success message and the application's `?success` route. Saved the confirmation locally and added one confirmed entry to the application ledger.
10. **Complete post-submission steps.** Submitted the optional EEO survey using saved demographic preferences and verified its separate success message. Sent the Discord result and read the delivered message back to verify its content. Google Sheets tracker synchronization was intentionally skipped.
11. **Close the control session.** Stopped the task-local CDP worker and left the final confirmation page open in normal Chrome. A later queued worker-readiness notice was not another application or another submission.

### Trips, issues, and successful recoveries

| Issue observed | What resolved it | Lesson |
| --- | --- | --- |
| Ordinary extraction returned a title and short description, not the full requirements. | Read the complete rendered official posting before filling the form. | A sparse extract is not evidence that there are no eligibility requirements. |
| The Hermes native file picker did not respond reliably to automation; native window discovery also became inconsistent. | Used the exact existing normal-Chrome application tab and attached the resume directly to its real file input through CDP. | Do not make the user perform the resume upload merely because one UI-control route failed. Recover through an authorized browser route and verify the real attachment. |
| Chrome's `/json/list` and `/json/version` returned HTTP 404. | Read the browser WebSocket address from the existing profile's `DevToolsActivePort` and verified a real CDP round trip. | Those HTTP failures alone do not prove that Chrome debugging is unavailable. Do not restart or replace the user's browser on that evidence alone. |
| A fronting command returned successfully while the target still reported `hidden`. | Activated the exact target, restored its window to a normal state, and confirmed `document.visibilityState === 'visible'`. | Successful command delivery is not proof that the user can see the application. Verify visibility before trusted input. |
| The resume upload changed the file input from required to optional after success. | Checked the same observed file input and the rendered filename instead of continuing to look only for `input[type=file][required]`. | A selector disappearing after an upload can be a state transition, not a failed attachment. |
| Workable's underlying radio `input.checked` did not reliably represent the selected answer, especially a false-valued No. | Read the rendered radio wrapper's `aria-checked` state and its associated question, label, and value after rerendering. | Validate the component's committed selection, not one DOM property in isolation. |
| The salary control normalized `$22/hour` to numeric `22`. | Read the saved numeric value back and checked it against the posting's hourly rate. | Verify what the control retained; do not assume the typed formatting survived. |

### Confirmation evidence

**Application confirmation observed in Workable:**

> Your application has been submitted successfully.

The page also stated that a copy would be sent to the applicant's email address. That is a statement from the confirmation page, not a claim that a receipt email was independently checked.

**Optional EEO confirmation observed after its separate submission:**

> Your EEO form has been submitted successfully.

**Additional verified outcomes:**

- The intended resume was attached before the application Submit action.
- Required answers were reviewed and the form had no invalid controls or visible validation alerts before submission.
- Exactly one confirmed Mindex entry was recorded in the local application ledger.
- The Discord notification's delivered content matched the message sent.
- The task-local browser-control process was stopped after completion.

The private evidence consists of the pre-submit field read-back, file metadata and resume hash, submission-intent record, application confirmation capture, ledger entry, and notification read-back. These records are retained locally, not published here. This Markdown is a sanitized account of observed results, not independently reproducible proof of an employer's private candidate record. A `?success` URL alone is not proof; the success text was actually observed after the submission.

The task-local intent record was not a substitute for the production controller's transactional authorization or cross-run submission fencing. This entry documents the route that actually ran, rather than manufacturing production-pipeline artifacts after the fact.

### Final result

**Confirmed submitted.** The agent completed resume upload and application submission end to end, recovered from the browser-control problems, verified both application and EEO acceptance, and delivered the result notification. No application-step blocker remained at the end of this run. Hiring outcome is unknown.

---

## Meta — Data Engineer Intern, Product Analytics (Summer 2027)

### Job and execution context

- **Official posting:** <https://www.metacareers.com/profile/job_details/1373603594867455/>
- **Requisition:** `1373603594867455`.
- **Locations:** Menlo Park, California; New York, New York; Seattle, Washington, United States.
- **Submission date shown by the portal:** October 3, 2026.
- **Execution mode:** An explicitly requested, concurrent application batch. One agent owned this exact employer/requisition and its normal-Chrome tabs; other agents worked on separate employers. A shared CDP connection routed commands to owned targets without starting replacement Chrome instances.

This was an agent-operated application in a live user session, not proof that the repository's scheduled controller supports Meta end to end. The agent handled email verification, resume upload, submission, and the supplemental disclosure; the coordinator independently checked the employer's result afterward.

### End-to-end flow

1. **Verify the exact posting and eligibility.** Read the full official US internship requirements and compare the technical degree, programming, and work-authorization requirements with the applicant's private sources.
2. **Check prior application evidence and authenticate.** Check the confirmed ledger, relevant browser history, and prior task evidence. Complete the site's email-code account flow through the authorized inbox and verify the authenticated account before filling the application.
3. **Upload and complete the actual form.** Attach the profile-selected current resume; select real offered locations; fill the rendered contact, current-location, website, and self-identification controls. The page did not request separate education and employment-history entries; the resume supplied that background.
4. **Review the rendered application.** Verify the exact resume filename and metadata, committed selections, applicant identity, and required visible controls. Keep unrelated shared-form placeholders distinct from questions actually presented by this version of the application; do not alter validation or invent hidden answers.
5. **Submit once.** Persist submission intent before dispatch. The response took approximately twelve seconds; the agent waited and read the page instead of clicking Submit again.
6. **Confirm the employer receipt.** Verify the exact role and dated Applied status on Meta's Applications page, then immediately add the confirmed application to the private ledger using the shared lock and an atomic write.
7. **Complete and verify follow-up items.** Resolve the government-employment disclosure from the canonical answer source, save it, and read it back through View responses. Verify that government employment disclosure, voluntary self-identification, and resume upload all show Completed. Check the saved resume filename through its separate View route.
8. **Independently reconcile the result.** The coordinator read the live application detail and Applications list, verified the single ledger entry, and delivered a Discord batch result with exact message read-back. Google Sheets synchronization was intentionally skipped.

### Trips, issues, and successful recoveries

| Issue observed | What resolved it | Lesson |
| --- | --- | --- |
| The configured mail API authorization was revoked. | Used the existing authorized Gmail session in a task-owned normal-Chrome tab to read the exact verification message without marking it read. | An unavailable API is not the same as an unavailable authorized inbox. Never print or persist verification codes or session secrets. |
| The heavy knowledge-document renderer timed out. | Read the document's official text export and retained only the narrow, non-secret answer needed for the disclosure. | Recover through an authorized source; do not dump a document containing mixed private material. |
| A shared validator described an unused employment-history placeholder. | Inspected the actual one-page section mapping and verified its rendered fields without changing validation or supplying fabricated history. | Distinguish actual application requirements from unrelated component defaults. |
| Submit did not return immediately. | Preserved the original intent and waited for the server-created application and receipt. | A slow response is not permission for another Submit. |
| Submission created supplemental tasks. | Completed the ordinary disclosure and verified all three task statuses separately. | Application receipt and follow-up completeness are separate checks. |

### Confirmation evidence and final result

The live Applications page displayed the exact role followed by:

> Applied Oct 3, 2026 • New York, NY, Menlo Park, CA, Seattle, WA

The application detail showed **Completed** for all three items: government employment disclosure, voluntary self-identification form, and resume upload. The private application reference, review, one-shot journal, receipt, saved-answer read-back, resume evidence, and notification receipt are retained locally rather than published here.

**Confirmed submitted, with the displayed follow-up items complete.** Only this verified submission from the concurrent batch is added to the success table. Blocked drafts are not counted as successful applications. No interview or hiring outcome is implied.

---

## Epic Games — three confirmed internship applications

### Jobs and execution context

All three positions were live, full-time internships in **Cary, North Carolina, United States**, with flexible starts in 2027. The submission times below come from the private confirmation records, converted to Pacific time.

| Role | Requisition / job ID | Official posting | Confirmed submission |
| --- | --- | --- | --- |
| Backend Services Programmer Intern | `R27435` / `6183293004` | [Epic posting](https://www.epicgames.com/site/careers/jobs/6183293004?lang=en-US) | October 5, 2026, 8:16 p.m. PDT |
| Data Science Intern | `R27453` / `6202675004` | [Epic posting](https://www.epicgames.com/site/careers/jobs/6202675004?lang=en-US) | October 5, 2026, 8:18 p.m. PDT |
| Technical Product Management Intern | `R27432` / `6178818004` | [Epic posting](https://www.epicgames.com/site/careers/jobs/6178818004?lang=en-US) | October 5, 2026, 8:19 p.m. PDT |

**Execution mode:** An explicitly requested, agent-operated batch using exact-target CDP in the existing normal Chrome. The agent prepared and submitted the forms sequentially, using one persistent browser connection. No replacement Chrome instance was launched. The user approved requesting a fresh browser connection after the first connection was rejected; the agent did not approve a browser permission prompt on the user's behalf.

This was a supervised live session, not an uninterrupted scheduled-controller run. The agent performed the resume uploads, field entry, option selection, review, submission, and confirmation checks. These results do not establish unattended production-controller support for Epic's branded form.

### End-to-end flow

1. **Screen every supplied posting.** Ordinary retrieval of Epic's branded pages returned blocked or incomplete content. Recovered complete current requirements and question schemas from Epic's public Greenhouse board API, then verified the eligible postings in normal Chrome. Checked each job's location, internship term, and degree/enrollment requirements independently rather than assuming sibling roles had identical eligibility.
2. **Reconcile duplicate evidence.** Checked the canonical confirmed-submission ledger and relevant browser history. The six-link request contained one prior exact-job confirmation and two eligibility exclusions; none was counted as a newly completed application or added as a success entry here.
3. **Recover the authorized browser connection.** Paused when Chrome rejected the first connection. After the user authorized a fresh connection, established a persistent approved browser WebSocket and restricted application operations to the task's exact targets. No security prompt was bypassed.
4. **Use the actual Greenhouse form.** Opened Epic's branded Apply control, identified its distinct custom-form structure, and moved to the underlying Greenhouse embed route for the same verified board and job IDs. Rechecked exact role, employer, and location before filling. The branded form was not submitted.
5. **Inspect and attach the current resume.** Inventoried each untouched Greenhouse form and education controls, resolved the designated resume from the private profile, and attached it to the observed resume input. Verified the displayed filename in each application and again during pre-submit review. Greenhouse removed the original file input after attachment; the original browser File metadata was not retained, and no downloaded-attachment hash verification is claimed.
6. **Fill truthful facts and commit real options.** Entered profile-backed identity, contact, location, education, current role, employer, and portfolio information. Selected real offered options for prior employment, referral source, sponsorship, work authorization, availability, experience, project samples, acknowledgements, and voluntary self-identification preferences. Used a truthful Other discipline option when the directory did not offer Data Science; no unrelated major was substituted. Re-inventoried after asynchronous parsing and preserved already-correct values.
7. **Review each complete form independently of the fill actions.** Read back actual values and committed chips, compared them with canonical applicant sources, and verified the intended resume, education dates, required consent, and exact job identity. Native invalid-control lists and visible validation alerts were empty; no visible human-verification challenge remained. Optional cover letters were omitted.
8. **Submit once per requisition.** Rechecked the confirmed ledger under a lock and created an exclusive per-requisition intent record before each Submit. Dispatched one application submission for each of the three roles. Waited read-only through navigation rather than replaying a click.
9. **Verify and record immediately.** Required the exact job's Greenhouse confirmation route and the rendered receipt text, then recorded that confirmed submission in the private ledger before progressing. After the last submission, independently read all three preserved confirmation targets again. Delivered the sanitized batch result to Discord and verified its exact message content by read-back. Sheets synchronization was intentionally skipped.
10. **Stop the controller.** Ended the task-local browser-control process after completion while leaving the confirmation pages intact. A delayed readiness notification was checked against the stopped process and did not restart application work.

### Trips, issues, and successful recoveries

| Issue observed | What resolved it | Lesson |
| --- | --- | --- |
| Branded-page requests returned HTTP 403, timeouts, or truncated qualification text. | Read the full official Greenhouse API payload and verified exact posting identity in the real browser. | Missing bullets are incomplete source evidence, not an absence of requirements. |
| Chrome rejected the initial automation connection. | Paused for user approval of a fresh connection; the renewed connection succeeded. | Keep the human permission boundary explicit instead of describing a supervised recovery as fully unattended. |
| Epic's custom form used different controls from modern Greenhouse. | Used the underlying Greenhouse form for the exact verified board and requisition before entering application data. | A shared ATS backend does not mean the branded wrapper supports the same selectors. |
| A previously backgrounded form completed resume parsing after activation, changing education IDs from `--0` to `--1` and prefilling dates and a contact link. | Re-inventoried the live form, resolved each unique current education control before use, and preserved correct values. | The first inventory and a successful upload filename do not mean asynchronous parsing has finished. |
| Country selection committed a `+1` chip, and the phone field reformatted the digits. | Checked the adjacent country label and normalized phone digits rather than insisting on the original typed formatting. | Abbreviated display and normal formatting are not failed bindings. |
| The discipline directory did not offer Data Science. | Selected its actual non-asserting Other option and verified the committed value. | Never substitute a different degree discipline just to complete a picker. |
| The first confirmation navigation briefly had an empty body. | Waited for the rendered receipt, then read it again without another Submit. | A new URL or page title is not sufficient by itself; preserve intent while the success page renders. |

### Confirmation evidence and final result

Each of the three exact Greenhouse job targets displayed:

> Thank you for applying.
>
> Your application has been received and if it seems like a good fit for the position, we will contact you soon.

All three confirmation routes matched their own job IDs. Each had exactly one confirmed ledger entry, and the delivered Discord summary matched its read-back. The private reviews, intent records, per-job confirmations, aggregate verification, and notification receipt remain local. Applicant data, browser/session identifiers, private message IDs, and raw artifacts are not published here.

**Three new applications confirmed submitted.** No application-step blocker remained for these three roles. Prior or excluded postings are not new successes; no interview, offer, email-receipt verification, or hiring outcome is implied.

---

## Adding future successful applications

Keep each entry short enough to inspect but specific enough to reproduce the successful approach:

1. **Identity:** Employer, exact role, public posting link, requisition, ATS, and submission date with timezone.
2. **Execution mode:** Visible or background; supervised or scheduled; the actual automation route used. Separate an agent-operated success from claims about a fully connected unattended pipeline.
3. **End-to-end flow:** Preflight, duplicate check, account handling if any, resume upload, field binding, review, one submission, and confirmation.
4. **Trips and recoveries:** Observed failure, attempted remedy, verified fix, and any unresolved limitations. Do not hide user intervention or count a workaround as a permanent code fix.
5. **Evidence:** Exact non-sensitive confirmation wording and independently verified follow-up outcomes. Keep application success, EEO success, email receipt, ledger writes, and notification delivery separate.
6. **Final result:** Count only confirmed submissions. Describe any remaining follow-up without implying an interview or offer.

Do not publish credentials, session tokens, applicant contact details, home addresses, demographic answers, resume contents, local home-directory paths, private message identifiers, or raw browser/network logs. Keep unconfirmed attempts out of the success table and do not resubmit an application just to obtain better documentation.
