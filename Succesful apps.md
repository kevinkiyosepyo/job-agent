# Succesful apps

A running record of real, confirmed job applications completed by the agent: what happened end to end, where the flow tripped up, what resolved it, and what proved the employer received the application.

**Successful means submitted and confirmed by the employer's application system.** It does not mean an interview, offer, or acceptance. A filled form, uploaded resume, Submit click, or notification alone is not a successful application.

This log starts with the verified Mindex run below. It is not a complete historical application count. Add future entries only after checking their own confirmation evidence.

## Confirmed applications

| Application date | Employer | Role | ATS | Requisition | Result |
| --- | --- | --- | --- | --- | --- |
| October 3, 2026 (PDT) | Mindex | Software Engineer Co-Op - On-site | Workable | `84B10DB922` | Application and optional EEO survey confirmed submitted |

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

## Adding future successful applications

Keep each entry short enough to inspect but specific enough to reproduce the successful approach:

1. **Identity:** Employer, exact role, public posting link, requisition, ATS, and submission date with timezone.
2. **Execution mode:** Visible or background; supervised or scheduled; the actual automation route used. Separate an agent-operated success from claims about a fully connected unattended pipeline.
3. **End-to-end flow:** Preflight, duplicate check, account handling if any, resume upload, field binding, review, one submission, and confirmation.
4. **Trips and recoveries:** Observed failure, attempted remedy, verified fix, and any unresolved limitations. Do not hide user intervention or count a workaround as a permanent code fix.
5. **Evidence:** Exact non-sensitive confirmation wording and independently verified follow-up outcomes. Keep application success, EEO success, email receipt, ledger writes, and notification delivery separate.
6. **Final result:** Count only confirmed submissions. Describe any remaining follow-up without implying an interview or offer.

Do not publish credentials, session tokens, applicant contact details, home addresses, demographic answers, resume contents, local home-directory paths, private message identifiers, or raw browser/network logs. Keep unconfirmed attempts out of the success table and do not resubmit an application just to obtain better documentation.
