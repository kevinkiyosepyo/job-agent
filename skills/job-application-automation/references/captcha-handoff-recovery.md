# CAPTCHA Detection, Handoff, and Resume

Use when an ATS page contains CAPTCHA/reCAPTCHA/hCaptcha/Turnstile scripts, widgets, checkboxes, challenges, or validation errors. This reference does not authorize clicking, solving, outsourcing, or bypassing a CAPTCHA.

## Distinguish Dormant Code from a Real Gate

1. Inspect the rendered page, not script names alone.
2. Treat CAPTCHA libraries, hidden containers, or empty response fields as dormant when no visible widget/challenge, validation error, or blocked Continue/Submit state exists.
3. If no real gate is rendered and the application advances normally, record `captcha_gate: false` and continue.
4. Treat any visible `I'm not a robot` checkbox, image/audio challenge, managed challenge, verification spinner, CAPTCHA error, or required CAPTCHA token as a genuine human gate. Do not click the checkbox or challenge.

## Genuine-Gate Handoff

1. Save the server-side draft when the ATS offers a safe Save Draft action before the gate.
2. Preserve the exact Chrome target ID, URL, company, role, requisition, current step, and verified field state.
3. Capture a scoped screenshot of the browser page without interacting with the challenge.
4. Notify Kevin immediately on Discord/Telegram: name the company/role, exact URL, current step, and say only `Complete the visible CAPTCHA in the preserved tab, then reply done.` Never include credentials or application answers.
5. Leave the exact tab open and do not navigate, refresh, duplicate, submit, or retry the CAPTCHA.
6. Wait for Kevin to complete it manually.

## Automatic Resume After Kevin Clears It

1. Rebind the same exact target and verify URL/job identity did not drift.
2. Confirm the visible challenge is gone or the page exposes a verified cleared/completed state. Do not read, print, or persist CAPTCHA token contents.
3. Re-read every field on the current step; CAPTCHA widgets can rerender or reset surrounding React state.
4. Continue from the next safe action. If Submit was not previously attempted, follow the one-shot authorization/Submit procedure. If Submit may have occurred, inspect confirmation without replay.
5. Verify portal confirmation, tracker read-back, and Discord read-back normally.

## Failure and Expiry Recovery

- If the challenge expires before Kevin completes it, preserve the draft and request one fresh human completion; do not automate retries.
- If the page reloads, reopen only the canonical exact application route and verify saved state before presenting the new gate.
- If the target, company, role, or requisition changes, stop and reacquire the intended application before any action.
- If a CAPTCHA remains after Kevin reports completion, capture fresh scoped evidence and ask Kevin to finish the remaining visible challenge.

## Verification

A CAPTCHA handoff is complete only when:

- the genuine challenge was completed by Kevin;
- the exact target/job identity is unchanged;
- the CAPTCHA no longer blocks the current step;
- surrounding field state has been reverified;
- no automated challenge click/solve/bypass occurred.
