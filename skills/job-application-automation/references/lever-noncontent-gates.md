# Lever non-content gate text

Use for public Lever snapshot inspection when stylesheet or script source mentions CAPTCHA. Through `terminal`, inspect the exact saved official HTML with `prepare_job.py <snapshot> --page-url <exact-url> --output <private-json>`; redirect bulky stdout to a private artifact rather than flooding the conversation with school directories.

The Lever inspector excludes text inside `script` and `style` from its static CAPTCHA text candidates. CSS selectors and JavaScript integration names are not rendered challenge evidence. The change leaves field inventory, option groups, static upload-filename checks and confirmation behavior unchanged. Ordinary surrounding challenge text still produces the existing candidate flag, including after non-content sections close.

Limits:
- `manual_gate: null` means no matching text in this narrow snapshot scope, not rendered CAPTCHA clearance, a verified token, safe interaction or permission to Submit.
- This is not a visibility engine. Templates, hidden elements, CSS class effects, iframes, attributes, JavaScript-rendered challenges and submit-time errors are not proven absent or resolved by this filter. Corroborate static flags with the approved fresh browser surface. In particular, `aria-hidden` is not visual hiding.
- Never click a CAPTCHA-owned button, alter tokens or bypass challenges. Preserve real human/security gates, unknown material facts and any existing uncertain submit intent. No isolated browser, new connection consent or source registry is enabled.
- API content and HTTP200 prove only their exact public response, not applicant eligibility or saved application state. Keep unselected public observations separate from seeded eligible pilot counts.

Verification through `terminal`: use the configured interpreter with `run_offline_tests.py tests/test_lever_noncontent_gates.py tests/test_lever_handler.py -q`, then the full guarded suite. Replay exact saved bytes and confirm the only result change is the justified static gate candidate; submission must remain disabled and all inventory/provenance identical. Retain the Chrome-launch exclusions. Saved snapshots never replace connected Review, byte provenance and authoritative confirmation.
