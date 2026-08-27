# ATS and Pipeline Details

## Shared Invariants

- Attach to Kevin's approved personal Chrome through CDP at `http://127.0.0.1:18800`; do not launch a clean profile when authenticated state matters.
- Before opening an application, check `~/Documents/job-agent/tracker.py` by exact normalized URL and normalized company/role.
- Meta, Amazon, Apple, Netflix, Google, and Microsoft, including clear subsidiaries, are manual-only. Notify Kevin on Discord before applying.
- Load canonical answers from `~/Documents/job-agent/profile.json`; never infer missing facts.
- Upload files by locating the real `input[type=file]` and calling CDP `DOM.setFileInputFiles`. Verify both `input.files[0].name` and the filename rendered by the ATS.
- Never bypass CAPTCHA, email verification, identity verification, or assessments. Leave the prepared tab open and notify Kevin.
- A click, spinner, disabled button, draft, or navigation is not proof of submission. Record `Submitted - Pending Response` only after an unambiguous confirmation page/message.

## Greenhouse

1. Inventory visible and conditional fields with DOM labels and the accessibility tree.
2. Focus each field explicitly, replace the complete old value, and re-read it after every write.
3. For custom dropdowns, dismiss Chrome autofill overlays, open the page-owned listbox, filter if supported, use Arrow Down, and press Tab to commit. Enter may highlight without committing.
4. Verify the country selector does not duplicate the `+1` phone prefix.
5. Confirm all required values, validation state, and resume filename before one Submit click.

## Workday

1. Treat every employer tenant as a separate account/session.
2. Follow the wizard: My Information → My Experience → Questions → Disclosures → Review → Submit.
3. Resume parsing is untrusted. Compare every parsed employer, title, date, school, degree, skill, email, and phone against the profile/resume and remove duplicates or hallucinations.
4. Re-inventory controls after every answer because conditional questions appear dynamically.
5. Save as Draft when interrupted; Workday sessions commonly expire quickly. A draft is never a submission.
6. Confirm the requisition and all sections on Review before submitting once.

## Deterministic Helpers

- `~/Documents/job-agent/tracker.py`: live GViz tracker reads, schema-preserving duplicate checks, OAuth-gated writes.
- `~/Documents/job-agent/scanner.py`: URL cleanup, ATS detection, eligibility filtering, dedup, and MAANGO routing.
- `~/Documents/job-agent/notifier.py`: deterministic Discord notifications with dry-run support.

Use dry-run fixtures for validation. Do not create fake production tracker rows or fake application-success notifications.