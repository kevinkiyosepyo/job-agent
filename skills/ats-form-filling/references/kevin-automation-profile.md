# Kevin Job-Automation Profile and Source Precedence

Use this only for Kevin Pyo's application workflows. Keep raw credentials, license numbers, OAuth tokens, and resume contents out of skill files; read them from the ignored local profile and authorized sources at runtime.

## Canonical sources

1. Current resume path from `~/Documents/job-agent/profile.json`.
2. Confirmed structured facts in that profile.
3. Authorized application-knowledge Google Doc ID `1zqr26fQKzwAgPMbdyYPoTDAcLKjGoQ4PKxMLug4hr-k`.
4. If a material answer remains unknown or sources conflict, fail closed and ask Kevin.

Historical ATS review text is evidence of previous form behavior, not automatically a fact. Ignore known autofill mistakes such as the wrong university, wrong education end year, wrong GPA, or an answer claiming Kevin is not an undergraduate.

## Confirmed application policies

- Permanent address: Fairfax, Virginia address stored in the profile; current location: San Diego, California.
- Driver-license state answer: California. Never infer or expose the license number unless the live form explicitly requires it.
- When a form requires a full date but only month/year is confirmed, use day `1`.
- Outside-business-activities answer: `No`, per Kevin's explicit instruction.
- Source/referral default: `Social Media`; if a child option is required, select `Instagram`, then `Facebook` as fallback.
- Compensation fallback when required: `$20/hour` or `$20,000 annual`, selecting a real range option when the control is dropdown-backed.
- Optional cover letters: skip.
- Demographics when asked: Male, Asian, not a veteran, disability `Decline to answer`.
- MAANGO companies (Meta, Amazon, Apple, Netflix, Google, Microsoft and clear subsidiaries): require Discord approval before applying.
- Discord token rotation is postponed by the user; do not block application engineering on it.

## Confirmed employment dates

Read exact values from `profile.json`. Known entries use the first day of the stated month. Qualcomm, HDSI/Smarr Lab, MyEMSPath, and Handshake have confirmed dates. HNRC's exact start month remains unknown: if a form requires it, stop and request the missing month rather than guessing.

## Interaction preference

Kevin prefers action over repeated routine confirmations. For an already-authorized application task, click routine setup, consent, and continue controls and verify the result. This does not override manual-only gates: CAPTCHA/hCaptcha, password/2FA/login walls, assessments, identity verification, ambiguous legal attestations, MAANGO approval, purchases, or destructive account actions.
