# Modern Greenhouse upload questions

Use when a static upload input is labelled only `Attach` or appears optional despite a question wrapper. A native file picker label describes the action, not necessarily the document question.

The Greenhouse inspector recognizes a nearest `.file-upload[role="group"]` with one `aria-labelledby` reference to one unique in-group `.upload-label`, one descendant file input and a globally unique input ID. It replaces only blank/`Attach` labels with the wrapper question. An explicit specific control label is preserved. Group `aria-required="true"` can add a requirement but never clear a native requirement. Adjacent resume, cover letter, portfolio and transcript uploads stay separate.

Missing/duplicate IDs, multiple file inputs, external label references, ambiguous references and unsupported wrapper shapes retain their raw inventory rather than borrowing another question. This is a narrow static interpretation, not complete upload coverage or rendered validity. Unknown file requirements remain blockers through preparation instead of becoming optional generic `Attach` actions.

Procedure:
1. Preserve the complete official page and inspect the exact upload wrapper; do not infer the document from file order or basename.
2. Inspect `fields` for document label, input name/type and required flag. Keep optional cover letters optional. An allowed extension is not permission to use a different document.
3. For real uploads, use the approved exact-bound browser file input and canonical document source. Static labels, filename text, or a known document path do not prove uploaded bytes, successful attachment, saved Review or submission.
4. Re-inventory after parsing/rerendering. Verify the required document and its file evidence independently on Review. Unknown or unsupported controls remain blocked.

Verification through `terminal`: configured interpreter with `run_offline_tests.py tests/test_greenhouse_upload_questions.py tests/test_greenhouse_handler.py -q`, then full guarded suite. Replay complete saved pages and require non-file fields, control hints, choice groups, identity and gate state to remain unchanged. Confirm known-answer evidence does not increase from label recovery alone and no browser mutation is performed by replay.
