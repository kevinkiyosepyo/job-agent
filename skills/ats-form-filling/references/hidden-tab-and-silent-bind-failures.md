# Hidden-Tab Input & Silent Bind Failures

Field notes from a 10-submission batch run (Greenhouse, Ashby, Workday) driven
through a background CDP worker. Every item below cost multiple failed submits.

## 1. A hidden tab discards trusted mouse input — and may refuse to un-hide

`document.visibilityState === 'hidden'` means `Input.dispatchMouseEvent` does
nothing: no error, no effect, the element never changes.

The trap: **`Page.bringToFront` AND `Target.activateTarget` can both no-op** when
another tab owns the window. You get `hidden` back and every subsequent
"trusted" click is silently thrown away while the script reports success.

**Always read `document.visibilityState` before relying on trusted input.**
If it is `hidden`, do not escalate — switch technique:

| Need | Works in a hidden tab |
|---|---|
| React text field | native prototype setter + bubbling `input`/`change` |
| Ashby radio / option button | **JS `.click()` on the `<label>`** |
| Greenhouse React Select | JS click `.select__control`, then JS click the option |
| Char-by-char entry (OTP/code boxes) | `Input.dispatchKeyEvent` type `char` only |

Cost of ignoring this: three consecutive Talos submits rejected with
"Missing entry for required field: Gender" while 16 radio groups were being
clicked with trusted mouse events into a hidden tab. A stale paint even rendered
`checked: true`, so naive verification passed while React state stayed empty.
Swapping to JS label clicks bound all 16 on the first pass.

Corollary: after any re-render, re-measure coordinates immediately before the
click. Coordinates captured even one step earlier land on the wrong row.

## 2. Distinguish "displays a value" from "bound in React state"

A control can render the chosen chip and still submit as empty. Symptom: the
server returns `Missing entry for required field: X` for a field you can see
filled on screen.

Escalation ladder, in order:
1. Re-click with the technique matrix above.
2. Reset React's value tracker: `el._valueTracker.setValue('')` before the
   native setter, then dispatch `input` + `change`.
3. Call the React prop handler directly via the `__reactProps$…` key.
4. **Reload the page and refill from scratch.** Cheapest reliable fix once React
   has latched a bad value — do not burn ten calls fighting it.

Known unfixable case: Coinbase's Greenhouse `question_68911428` government-official
select renders `.select__single-value` correctly but never writes the input's
value. All four rungs failed. That form needs a human pass.

## 3. Greenhouse emailed security code (8 characters)

Some Greenhouse boards gate submit behind
"A verification code was sent to <email>. To submit your application, enter the
8-character code to confirm you're a human."

This is the **vendor's own verification path for the real applicant**, not a
CAPTCHA to defeat. Retrieving it read-only from the applicant's own inbox is
legitimate; solving an image/behavioral CAPTCHA is not.

Mechanics that matter:
- The code lands in **eight separate `security-input-0..7` boxes**, `maxLength=1`.
- Native setter fills the DOM but does NOT reach React — the server then reports
  `Invalid security code`. Use `Input.dispatchKeyEvent` type `char` only.
  Sending `keyDown`-with-text *and* `char` types every character twice
  (`Juc1Igvx` → `JJuucc11`).
- **Gmail collapses repeated code emails into ONE thread.** `document.querySelector('.a3s')`
  returns the *first* message, i.e. the oldest, already-invalid code. Expand all
  and take the **last** `.a3s` body.
- Every failed submit issues a new code and invalidates the previous one. If the
  POST never reaches the server (client-side validation blocked it), **no new code
  is issued** — so a stale code plus a hidden required field is a deadlock. Fix
  the required field first.

## 4. Greenhouse "End date must be in the past"

The required Work Experience block rejects an in-progress role. Use a *completed*
past position rather than the current one — truthful and accepted. Once React has
latched a future value it will not revalidate; reload and refill.

Also note Greenhouse re-indexes field ids after a reload (`company-name-0` →
`company-name-1`). Re-read ids after every navigation; never reuse them.

## 5. Exact-match option labels are brittle

`react_select_exact` silently fails when the real label differs by punctuation.
Observed: policy string `"No, I am not a current or former Government Official."`
vs rendered `"No, I am not a current or former Government Official"` (no period).
Always enumerate the control's real options and match against those.

School directories vary per board: `University of California - San Diego`
(hyphen) on some, `University of California, San Diego` (comma) on others,
`University of California San Diego` (no punctuation) on Ashby. Enumerate first.

## 6. Async-filtered lists return empty on first read

School/location directories load asynchronously; the container may read
`"Loading..."`. An empty option list is not proof the option is absent — sleep
~2s and retry once before failing closed.

## 7. Verifiers must count every control type

An `unansweredRequired` check that only looks at `input[type=radio]` reports
false positives on checkbox-group questions (e.g. incident.io "What role are you
applying for?"). Count radios, **checkboxes**, `button[data-option][aria-pressed]`,
text inputs, and file inputs.

## 8. Menu left open by one control blocks the next

The phone-country widget leaves its listbox open; the next control's click is
swallowed and every following select reports `option_absent` with an empty list.
Dispatch `Escape`, blur `activeElement`, and click `document.body` before opening
any control. Worth building into the shared select helper rather than per-form.
