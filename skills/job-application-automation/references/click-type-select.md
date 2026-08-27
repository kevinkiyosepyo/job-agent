# Reliable Click, Type, and Select Actions in ATS Forms

Use this reference whenever interacting with a Greenhouse, Workday, Lever, Oracle, LinkedIn, or custom employer application form. ATS controls are stateful applications, not static HTML. A visible label or typed text is not proof that the control accepted the value.

## Non-negotiable action loop

For every control:

1. Inspect the current rendered page and accessibility tree.
2. Identify the control by its visible label, role, nearby text, and current value. Never reuse an old element reference after navigation, opening a menu, validation, or conditional-field change.
3. Bring the control into view and focus it explicitly.
4. Perform exactly one action.
5. Re-read the rendered state and underlying value.
6. Only continue when the intended state is visible and the control has no relevant validation error.

If the post-action state is ambiguous, stop and re-inspect. Do not stack more clicks or keystrokes onto an uncertain state.

## Before any action

- Capture a fresh screenshot when layout, overlays, or focus are unclear.
- Read the visible label and surrounding question; do not infer a field from placeholder text alone.
- Determine the control type: native input, textarea, checkbox, radio, native select, custom combobox, date picker, file input, or button.
- Check whether the control is disabled, hidden, covered by an overlay, inside an iframe, or conditionally rendered.
- Confirm the target job, company, requisition, and current application step before changing fields.
- Prefer a stable semantic locator or accessibility-tree node over coordinates. Use coordinates only after visual confirmation and only for the current screenshot.
- Browser application controls must stay inside CDP/browser automation. Never use terminal-driven `osascript`, System Events `click at`, `cliclick`, pyautogui, or any global desktop coordinate fallback for an ATS page.
- If browser/CDP interaction is unavailable, stale, or blocked, stop with evidence. Do not switch to system-wide clicking, because Retina scaling or focus drift can hit the Apple menu, About This Mac, System Settings, or unrelated applications.
- When native browser chrome must be controlled, use scoped `computer_use` with a fresh capture of the named browser app, element indices first, `capture_after=True`, and no menu-bar interaction.

## Click protocol

1. Re-snapshot immediately before clicking.
2. Click the center of the visible control, not its label edge, unless the label is the only reliable hit target.
3. Wait for the smallest state change needed: menu visible, focus ring, checkbox state, page transition, or validation result.
4. Re-snapshot/re-read after the click.
5. If nothing changes, diagnose before retrying: wrong target, overlay, disabled control, stale reference, iframe, or click intercepted.
6. Retry at most once after re-inspection. Then leave the page unchanged and report the blocker.

Never use repeated blind clicks, coordinate guesses from a previous viewport, or a click followed immediately by a long sequence of actions.

## Typing protocol

For text inputs:

1. Focus the field explicitly.
2. Select all existing text through the control's normal keyboard behavior.
3. Type the complete intended value once.
4. Trigger the control's expected commit event with Tab or the form's visible next action; do not press Enter unless the form clearly uses Enter to submit or select.
5. Re-read the field value and confirm it exactly matches the intended value.
6. Check for an inline validation error.

If the value is truncated, duplicated, inserted into the wrong field, or not reflected after blur:

- Stop.
- Re-focus the field.
- Clear it through the UI.
- Type again more slowly or in one controlled fill operation.
- Verify before proceeding.

Do not type into a dropdown merely because it looks text-like. First classify whether it is a combobox.

## Native select protocol

For a real `<select>`:

- Use the actual option value/index through the browser automation interface when available.
- Re-read both the visible selected label and the underlying selected value.
- Do not type arbitrary text into the select.
- Confirm the form no longer reports the field as missing.

## Custom combobox protocol

For Workday/Greenhouse-style custom pickers:

1. Focus the combobox and record its current visible value.
2. Click the control once to open its page-owned listbox.
3. Verify that a listbox/options actually appeared; do not assume it opened.
4. If searchable, type a distinctive substring into the combobox search input.
5. Inspect the rendered options and choose the exact matching option row.
6. Prefer Arrow Down then Tab to commit when the ATS uses keyboard navigation. Enter may highlight an option without binding it.
7. Re-read the selected chip/button/value after the menu closes.
8. Reopen the control once if necessary to confirm the intended option remains selected.
9. Check validation state before continuing.

For nested source fields, select the parent category and then a concrete child option. Example: Social Media → Instagram or Facebook. A visible parent value alone may not satisfy validation.

## Checkboxes and radios

- Inspect the current checked/selected state before clicking.
- Click only when the current state differs from the intended state.
- Re-read `checked`, `aria-checked`, or the visible selected styling.
- Never toggle blindly; a second click can undo a correct selection.
- For required consent/disclosure controls, capture the exact label before choosing.

## Date controls

Treat visible date text as untrusted until the ATS accepts it.

1. Open the date widget.
2. Select month/day/year through the actual picker when possible.
3. If typing is supported, fill the complete date in the displayed format.
4. Blur with Tab.
5. Re-read the field and advance once.
6. If the form still says the date is required, the visible text did not bind. Reopen the widget and select through its real controls.

Do not use date shortcuts or guessed keyboard sequences across different ATS tenants.

## Buttons and Continue/Submit

Before clicking Continue, Save, or Submit:

- Re-read every required field on the current page.
- Confirm no hidden validation error is present.
- Confirm the correct resume is attached where applicable.
- Confirm the button is enabled and belongs to the current step.
- Click exactly once.
- Wait for the next step, confirmation message, or validation response.
- Do not click again because a spinner is slow.

A draft, navigation, spinner, disabled button, or URL change is not proof of submission. Submission requires the exact confirmation evidence defined in the parent job-application skill.

## Overlays, focus, and stale references

Common causes of apparent click/type failure:

- Chrome autofill popup covering an ATS menu
- A stale accessibility reference after the DOM changed
- Focus remaining in a combobox while the next value is typed
- A transparent validation layer intercepting clicks
- An iframe or shadow-root control
- A page transition that completed visually but not internally
- Browser viewport or zoom changing coordinate locations
- A disabled button that looks enabled

Recovery order:

1. Re-read page state.
2. Dismiss only the visible overlay with Escape or its close control.
3. Re-snapshot.
4. Re-identify the control.
5. Retry one action.
6. If still blocked, capture evidence and stop rather than brute-forcing.

## Verification evidence

For each critical interaction, retain enough evidence to debug:

- Job URL and requisition/company
- ATS platform and current step
- Field label
- Intended value
- Post-action visible value
- Underlying selected/checked state when accessible
- Validation message, if any
- Screenshot for ambiguous or failed interactions

For uploads, verify both the actual file input filename and the filename rendered by the ATS after save/continue.

For submissions, verify the confirmation page/message or candidate-home application entry, then log the exact evidence before notifying the user.

## Manual gates

Stop and notify the user for:

- CAPTCHA, hCaptcha, reCAPTCHA, email verification, or identity verification
- Assessments or timed tests
- Ambiguous legal, sponsorship, disability, demographic, compensation, or relocation questions
- A control that remains ambiguous after one inspected retry
- Any action that could submit a duplicate application

Leave the prepared tab open. Never bypass the gate or claim success without evidence.
