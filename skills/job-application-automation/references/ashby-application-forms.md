# Ashby Application Forms

## Verified completion pattern

Use for official `jobs.ashbyhq.com/.../application` forms.

1. Open the direct `/application` URL and wait for the dynamic form to replace the **Fetching application form** state before inventorying or filling.
2. Upload the exact resume and any required supporting document with `DOM.setFileInputFiles`; re-read both `input.files[0].name` and the rendered filename.
3. For React-controlled required text fields, do not accept a DOM value alone as proof. Enter the final value with trusted browser keyboard input (focus field, clear it, then `Input.insertText`), because synthetic DOM value assignment plus input events may look correct but fail Ashby server-side validation.
4. Inspect every required yes/no control. Ashby can mix radio groups with button-backed `data-field-path` controls. For button-backed controls, click the rendered `button[data-option='yes'|'no']` and verify `aria-pressed="true"`; do not infer that similarly worded earlier questions cover later required fields.
5. Submit once and read back an explicit confirmation such as: `Your application was successfully submitted.` Only then append the tracker.

## Required documents

When a posting requests a transcript, locate the exact user-specified file path rather than relying on stale cached paths. Confirm it is a local PDF before upload.
