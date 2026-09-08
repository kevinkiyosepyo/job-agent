# Truthful auto-answering of ATS screening questions

Hard-won rules for any code path that answers ATS questions programmatically.
Written after a Greenhouse batch run in which a generic fallback came within one
keystroke of submitting false legal statements under Kevin's name.

## The incident (why this file exists)

An auto-resolver was given a "fill anything still invalid" fallback:

```python
if val is None:
    val = "Yes" if label.strip().endswith("?") else "N/A"   # NEVER DO THIS
...
r = set_combo(t, fid, cands or ["Yes"], None)               # NOR THIS
```

On a Northmarq application it produced, all displayed as valid and ready to submit:

| Question | Auto-answer | Truth |
|---|---|---|
| Will you now or in the future require visa/status sponsorship? | **Yes** | No |
| Have you ever worked for Northmarq? | **Yes** | No |
| Are you currently employed by Northmarq? | **Yes, full-time** | No |

Three false statements, two legally material. They were caught only because a
pre-submit read-back compared every field against the profile. Nothing in the
form's own validation flagged them — to the browser the form was complete and
correct.

A second variant of the same bug: the resolver checked **every** salary band plus
"Commission" in a compensation checkbox group, because each unchecked box reported
`checkValidity() === false` and the fallback "satisfied" them all.

## Rule 1 — Unknown questions block submission; they are never guessed

An auto-resolver may answer only what it maps with confidence. Everything else is
appended to an `UNRESOLVED` list and prevents Submit:

```python
UNRESOLVED.append({"field": fid, "label": label, "kind": kind,
                   "options": rendered_options[:8]})
continue          # do NOT invent a value
```

Report unresolved items explicitly in the run summary. **A run that halts with
unresolved questions is a success, not a failure** — it means the guard worked.
Silence plus a submitted application is the dangerous outcome.

## Rule 2 — Anchor patterns tightly, order most-specific-first

A loose pattern is indistinguishable from a guess. This entry:

```python
(r"what degree are you (currently )?pursuing|degree are you pursuing", "Bachelor's")
```

matched five unrelated comboboxes on one Aquatic Capital form and wrote
`Bachelor's` into **GPA**, **Current Location**, **Location Preference**,
**employment-eligibility status**, and **internship history**.

- Anchor with `^` wherever the question has a stable opening.
- Put narrow patterns before broad ones; first match wins.
- Never let a value-bearing pattern (a degree, a city, a GPA bucket) sit above
  generic Yes/No patterns without an anchor.
- After any bulk pass, re-read every field's bound value and diff against intent.

## Rule 3 — Employment-history and legal questions default to NO

For a new employer these are false unless the profile says otherwise:

- "Have you ever worked for / been employed by <company>?" → **No**
- "Are you currently employed by <company>?" → **No**
- "Are you related to / do you have a relative at <company>?" → **No**
- "Non-compete, restrictive covenant, felony, debarment?" → **No**
- "Do you require sponsorship now or in the future?" → **No** (US citizen)
- "Are you authorized to work in the US?" → **Yes**

Graduation-window questions must be computed from the real date, not defaulted:
Kevin graduates **May 2028**, so "Are you graduating in the summer or fall of
2027?" is **No**, and a "graduating before September 2027?" gate is **No**.

## Rule 4 — Verify before Submit, including fields you set yourself

Writing a value is not the same as binding it. Observed silent corruptions:

- **Name doubling** (`KevinKevin`) when a second write lands mid-rerender.
- **Wrong city retained** — a location combo showing `Washington, District of
  Columbia` after `San Diego` was selected.
- **`+1` in EEO combos** — the phone country code bound to gender/race/ethnicity.
- **Displayed-but-uncommitted selects** — the wrapper shows the right label while
  the inner input still fails `checkValidity()`. Fix by focusing the control,
  pressing `Backspace` a few times to clear, then re-picking.

Read every field back from the DOM, compare to `profile.json`, and only then
submit. For option-backed controls read the value from the control's **own**
subtree (`[class*="singleValue"]` walking up from the input) — collecting all
`singleValue` nodes globally and matching by index leaks adjacent questions'
values and produces false "verified" results.

## Rule 5 — Checkbox groups need group-aware validity

Every unchecked sibling in a required checkbox group reports
`checkValidity() === false`, even when the group is satisfied. A naive gate
blocks submission forever; a naive *fallback* checks every box. Treat a group as
satisfied when any input sharing the `question_<id>[]` prefix is checked:

```javascript
if (e.type === 'checkbox') {
  var base = (e.id || '').split('[]')[0];
  var any = false;
  document.querySelectorAll('input[type=checkbox]').forEach(function (c) {
    if ((c.id || '').indexOf(base) === 0 && c.checked) any = true;
  });
  if (any) return;   // group satisfied — not an error
}
```

Pick exactly one truthful option in a source/referral group; for a compensation
band pick only the band matching Kevin's $20/hr default and uncheck the rest.

## Rule 6 — Essays are grounded, never generic

Required free-text prompts ("Why <company>?", "What motivates you?", "What is the
hardest thing you have done?") must be written from Kevin's actual record — UC San
Diego Data Science, the Qualcomm Institute software engineering internship,
Python services and data pipelines for research computing — and tied to the
specific role. Do not reuse a generic paragraph across employers, and do not
invent projects, metrics, or claims not present in the resume or profile.

Some ATSs take the essay as a **file upload** rather than a textarea (see
`div.file-upload` with `accept=".pdf,.doc,.docx,.txt,.rtf"`). A valid PDF can be
generated from the stdlib alone when no converter is available; verify the result
is text-extractable before attaching it.
