# Modern Greenhouse React preflight and one-shot submission

Use this reference for current Greenhouse forms that render React Select controls, hidden required companion inputs, asynchronous uploads, or inline submission errors.

## Pre-submit validity gate

Before issuing a one-shot authorization or recording submit intent:

1. Reacquire every live control after each React rerender.
2. Verify the framework-rendered selected value, not only the input DOM property.
3. Run the browser’s native form validity check and enumerate every invalid control, including hidden `required` companion inputs:

```js
const form = document.querySelector('form');
const invalid = [...form.elements]
  .filter(el => typeof el.checkValidity === 'function' && !el.checkValidity())
  .map(el => ({ id: el.id, name: el.name, type: el.type }));
({ valid: form?.checkValidity() === true, invalid });
```

4. Confirm there are no visible field errors or `aria-invalid="true"` controls.
5. Only after those checks pass may the operator journal submit intent and activate Submit once.

A checkbox with `element.checked === true` is not sufficient evidence on a React form. The framework state and any hidden required companion input must also be bound, and the field’s validation error must be gone. Prefer the control’s normal click/change path and verify native validity afterward; do not rely on direct `checked` assignment plus synthetic change events alone.

## React Select controls

- Opening or selecting may require the normal `mousedown` → `mouseup` → `click` sequence; a bare DOM `.click()` may not open the menu.
- Filter once, select one exact visible option, then poll the rendered `.select__single-value` until it equals the expected selected label.
- Some option text and selected text differ (for example `United States +1` may render as `+1` after selection). Store both the exact option text and expected selected label.
- Dynamic education IDs can change after resume parsing. Re-inventory and use unique input-prefixed selectors such as `input[id^='school--']`, never a stale numeric index.
- A selected control may hide or collapse its search input. Treat the rendered selected value plus cleared validation as the evidence; do not fail merely because the search input is no longer visually prominent.

## Resume upload

Greenhouse may replace the file input after upload. Poll until the exact profile-selected basename appears in the application’s rendered resume slot. The absence of the original `<input type=file>` after a successful attachment is not itself a failure. Preserve the profile resume hash from local preflight and require the exact rendered basename before Review.

## CDP and long-form notes

- For `websocket-client` against loopback Chrome CDP, omit the synthetic Origin header (`suppress_origin=True`) rather than weakening Chrome with a broad `--remote-allow-origins=*` policy.
- Scroll each long-form control into view before visibility/unobscured checks or mutation. Do not require every control on a long page to be simultaneously inside the viewport.
- Hidden file inputs are valid CDP upload targets when they are unique, enabled, and type `file`.

## Recovery after Submit

If a one-shot submit intent has already been journaled and the page returns inline validation instead of confirmation, do not replay Submit automatically. Preserve the exact tab, inspect the invalid field, and reconcile confirmation without replay. Record the binding bug for the next application so native validity is checked before intent.

Never claim success without explicit confirmation text, a reference, or a matching Candidate Home/application record.