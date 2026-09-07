# Kevin Pyo — Application Profile Reference

## Authority and freshness

This reference is an orientation aid, not a second source of application facts. Read `~/Documents/job-agent/profile.json`, its exact approved primary resume, and the current umbrella skill before filling a form. Explicit newer confirmations override historical resume/autofill errors. If sources still conflict on a material fact, hold that application for clarification; never silently revive an older default.

Do not dump the application knowledge Google Doc: it can contain credentials mixed with historical text. Retrieve only the non-secret answer window for the exact question, using the umbrella's filtering rules.

## Confirmed identity and education

- Full name: Kevin Kiyose Pyo
- Application email: kevinkpyo@gmail.com
- Phone: (571) 435-5734
- Citizenship: U.S. Citizen
- University: University of California, San Diego
- Degree: B.S. Data Science, in progress; Sep 2024–May 2028
- Confirmed cumulative GPA: **3.236**. Use the same accurate GPA whether or not a transcript is requested.
- LinkedIn: https://www.linkedin.com/in/kevin-pyo/
- Website: https://kevinpyo.com
- Address, employment titles/dates/descriptions, and sensitive driver's-license facts: obtain from the canonical profile/current approved resume for the specific field. Historical examples in other documents are not confirmed current facts.

## Resume selection

- Primary file: resolve `profile.json -> resume.primary` at run time.
- Required displayed/uploaded filename: the exact basename of that path, not a hardcoded `Resume.pdf`.
- Enforce the full `resume.do_not_use_for_applications` list.
- Do not rename/substitute a file to satisfy a stale implementation constraint. Report the adapter incompatibility.
- Verify the local file, browser upload, and actual ATS review/attachment evidence under the applicable submission contract.

## Application preferences

- Use target roles, eligibility, locations, and approved availability from the current canonical profile and umbrella skill. Winter/full-time internships are acceptable; do not invent a school-schedule conflict.
- Soonest availability: September 2026; specific future role dates still require truthful availability evidence.
- Optional cover letters: skip.
- MAANGO: exact-role approval required before application mutation/submission as specified by the umbrella.
- Recurring automation: at most one successful eligible non-MAANGO application per hour; no catch-up bursts. Load `references/hourly-new-job-pacing.md`; uncertain submit intent also prevents moving to a second application in that run.
- No Google Sheets reads/writes by default. Tracker synchronization must be explicitly requested.
- Use `references/screening-answers.md` for common answers and the current ATS child for real option selection.
