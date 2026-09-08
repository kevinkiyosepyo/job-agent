# Workday Tenant Control Selectors and Option Variance

Learned during a completed Marvell (`marvell.wd1.myworkdayjobs.com`) submission. The wizard **structure** repeats across tenants; **labels and option text do not**. Never carry a remembered option string to a new tenant — enumerate what is actually rendered.

## Selectors: `id`, not `data-automation-id`

Wizard form inputs are addressed by `id`. Many carry **no** `data-automation-id` at all — only the wrapping `formField-*` div does. A helper that resolves `data-automation-id` only will report `missing:` for every field and look like a broken page when the page is fine.

Make the resolver accept either, falling back through:
`document.getElementById(key)` → `[data-automation-id="key"] input, textarea` → `[data-automation-id="key"]` → raw selector.

Create Account page (these *do* use `data-automation-id`):

| Purpose | Selector |
|---|---|
| Email | `[data-automation-id="email"]` |
| Password / confirm | `[data-automation-id="password"]`, `[data-automation-id="verifyPassword"]` |
| Consent checkbox | `[data-automation-id="createAccountCheckbox"]` |
| Submit | `[data-automation-id="createAccountSubmitButton"]` |
| **Honeypot — leave empty** | `[data-automation-id="beecatcher"]` (`name="website"`) |

`beecatcher` is a bot trap. Never fill it; verify it is empty before submitting.

Later steps use `id`:

```
source--source                      How Did You Hear About Us (button)
country--country                    usually prefilled
name--legalName--firstName / --lastName
address--addressLine1 / --city / --postalCode
address--countryRegion              State (button)
phoneNumber--phoneType (button) / phoneNumber--phoneNumber
education-<n>--school / --degree / --fieldOfStudy
workExperience-<n>--jobTitle / --companyName / --location
workExperience-<n>--{start,end}Date-dateSection{Month,Day,Year}-input
primaryQuestionnaire--<hash>        one per application question
personalInfoUS--gender / --ethnicity / --veteranStatus
termsAndConditions--acceptTermsAndAgreements
selfIdentifiedDisabilityData--name / --dateSignedOn-dateSection{Month,Day,Year}-input
<hash>-disabilityStatus             three checkboxes
pageFooterNextButton / pageFooterBackButton
```

`<n>` in `education-42--…` / `workExperience-316--…` is assigned at render time and **changes** when a card is re-added. Discover it live:

```javascript
document.querySelector('input[id^="workExperience-"][id$="--jobTitle"]')
        .id.match(/workExperience-(\d+)--/)[1]
```

IDs starting with a digit (disability checkboxes) are invalid CSS selectors — use `[id="64cbff5f…"]`, never `#64cbff5f…`.

Map each question to its control by pairing the `formField-*` wrapper's first line of text with the control inside it; the `primaryQuestionnaire--<hash>` ids are opaque and tenant-specific.

## Option text varies per tenant — enumerate, then verify the binding

Canonical answers are *intents*; the rendered label is tenant-specific. Confirmed divergences at Marvell:

- **No `Social Media` option existed at all.** The documented two-step Social Media → Instagram referral flow does not exist on every tenant. The list held 38 job-board entries (LinkedIn, Indeed, Glassdoor, Campus Recruiting, Marvell Website, "Saw on Twitter feed"). When the canonical two-step is absent and the field is required, enumerate the real list and **ask Kevin** rather than substituting a near-match.
- **Veteran status** rendered `I AM NOT A VETERAN` (uppercase), not "I am not a protected veteran."
- **Ethnicity** rendered `Asian (Not Hispanic or Latino) (United States of America)`, not "Asian."
- **Degree** offered both `BS` and `Bachelor of Science (BS)`. A fuzzy `Bachelor` match silently selected **`Bachelor of Arts (BA)`** — wrong degree, bound without error. Try exact candidates first and compare the bound text to the intent before moving on.
- **Field of Study *did* contain `Data Science`.** Jumping to `Other`/`Information Science` is a *fallback*, not a first move — search the directory before falling back.

Rule: open the control, read every rendered option, select by exact string, read the button's `innerText` back, and compare. When no exact candidate matches, log the option list so the mismatch is visible instead of silently approximated.

## Typeahead pickers: Enter, then a re-measured click

School and Field of Study are typeahead multiselects. Marvell states it in the UI: "start typing the name … and press Enter."

1. Set filter text with the native setter (full system name, e.g. `University of California`).
2. Click the input, then dispatch real `rawKeyDown` / `char("\r")` / `keyUp` Enter events. Without Enter the directory never queries.
3. Locate the exact option, `scrollIntoView`, **wait ~1.2s for the scroll to settle, then re-measure** the box and click.

Step 3 is the one that bites. A box measured before the scroll settles misses silently — the list stays open, the field still reads `0 items selected`, and it looks like the option rejected the click. Re-measuring after settle fixes it.

Confirm by **chip text, not input value**: a successful selection leaves the input empty and renders `1 item selected, <label>`.

`University of California - San Diego` (spaced hyphen) is this directory's real UCSD entry and is an accepted variant.

## Dates: year first, expect unpadded read-back

Set `Year`, then `Day`, then `Month`; month-before-year can clear the month. Read-back returns unpadded values (`"6"`, not `"06"`) while the field displays `05/31/2028`. That is normal — compare numerically, not by string.

## Work Experience is a React field array that fails silently

Filling the card and advancing produced a Review page reading `Professional Experience — No Response`: every field had held on-screen, nothing persisted. **Education on the same step saved correctly**, so a saved sibling section is not evidence the array saved.

Recovery that worked: walk `pageFooterBackButton` back to My Experience, click Add again (new index), set **one field at a time with ~1.8s settle between writes**, read each value back, then Save and Continue and re-verify on Review. The second attempt persisted fully.

Always confirm Professional Experience on the server-rendered Review page before submitting.

## Gate check before Submit

Filter `[role="alert"]` for real blockers. A successful upload announces through the same channel (`"… successfully uploaded"`), so an unfiltered alert scan reports a false validation error and can block a clean submit. Exclude `successfully uploaded` before treating alerts as blocking.

## Submit and confirmation evidence

`pageFooterNextButton` doubles as **Submit** on the Review step. At Marvell, confirmation was:

- URL becomes `/jobTasks/completed/application`
- Title becomes `Candidate Home`
- My Applications shows `Active (1)` with job title, req ID, `Application In Process`, and submission date

When no reference number is issued, the Candidate Home row **is** the confirmation record. Read the row — navigation alone is not proof.
