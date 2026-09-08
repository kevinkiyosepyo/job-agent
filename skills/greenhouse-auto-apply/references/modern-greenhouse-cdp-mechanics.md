# Modern Greenhouse (job-boards.greenhouse.io) — verified CDP mechanics

Learned filing real applications (Scale AI, C3 AI). This is the `job-boards.greenhouse.io`
React form, not the legacy `boards.greenhouse.io` markup.

## The five failures that cost the most retries

1. **CDP mouse events cannot reach negative viewport coordinates.** After working a
   control low on the page, earlier fields sit at `y = -1243`. A click there is
   *silently dropped* — the field stays empty and NO error is raised. Always
   `scrollIntoView({block:'center'})`, sleep, then **re-measure** `getBoundingClientRect()`
   before dispatching. Treat `y < 0` as "not clickable yet", never as a missing field.

2. **React-select combos are 3–4px wide hidden inputs.** `document.getElementById('degree--0')`
   returns a control with `width: 4`, so clicking its own rect misses. Two working paths:
   - **Keyboard (preferred):** focus the input, dispatch `ArrowDown` to open the menu,
     `Input.insertText` a filter, then `Enter`.
   - **Wrapper click:** walk up parents until `width > 60 && height > 20`, scroll, re-measure,
     click that. Needed when the menu refuses to open from keyboard.

3. **Reading a combo's value from the input returns `""`.** The chosen label lives in a
   sibling `[class*="singleValue"]` node. Read it by walking up from the input to the first
   ancestor containing a `singleValue`. **Do not** collect all `singleValue` nodes and match
   by index — adjacent questions leak each other's values and you will "verify" a field that
   is actually empty. Verify per-control, scoped to that control's own subtree.

4. **The resume `input[type=file]` disappears after a successful upload.** `fileInputs: 0`
   is *expected post-upload*, not a failure. Confirm the attachment by the rendered text
   (`Resume/CV* | Resume 2027 SWE.pdf`), never by the input's existence. Locate the input
   structurally (any `input[type=file]` near a Resume/CV label) rather than by a fixed id.

5. **Education field indices drift.** `school--0` becomes `school--1` once the resume parses
   and a card is added. Re-read the current index (`input[id^="degree--"]` → regex the number)
   before every education write.

## Resume parsing can inject FALSE answers

Greenhouse auto-fill set **Disability Status = "Yes, I have a disability"** on both forms.
That is factually wrong for Kevin and is a legal self-identification. Always audit the EEO
block after upload and set it explicitly to his canonical values:
Gender `Male`, Hispanic/Latino `No`, Race `Asian`,
Veteran `I am not a protected veteran`, Disability `I do not want to answer`.
Set disability **last** — earlier writes can be re-applied by a later re-render.

## Authoritative completeness check

`e.willValidate && !e.checkValidity()` over every `input,textarea,select` is the reliable
gate. It catches id-less inner inputs that no label query finds. Iterate:
scroll the first invalid control into view → identify it by climbing to its nearest `label`
→ fill it → re-check, until the invalid list is empty. Do not submit while it is non-empty.

## CAPTCHA

`grecaptcha-badge` / reCAPTCHA **Enterprise v3** is a dormant background integration and is
**not** a gate. A naive `iframe[src*="recaptcha"]` check blocks every submission. Gate only on
a visible challenge outside `.grecaptcha-badge`, or literal "I'm not a robot" text.

## Submission is fast and can fire early

An `Enter` keypress inside a combo can submit the whole form. Before any Enter, ensure the
form is already complete and truthful. After submit, confirm by BOTH:
- URL ends `/confirmation`, and
- body contains `Thank you for applying.` / `Your application has been received.`

## Known option vocabularies

- School: `University of California - San Diego` (spaced hyphen; filter with `San Diego`)
- Degree: `Bachelor's Degree`
- Discipline: often **no** `Data Science` — `Computer Science` is the truthful closest match
  for Kevin's DS program when DS is absent; filter with `Comp`
- C3 AI graduation option: `May/June 2028`
