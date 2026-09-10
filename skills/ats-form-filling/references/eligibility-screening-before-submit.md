# Eligibility Screening Before Spending a Submit

A submit is irreversible and rate-limited (Kevin's cap: one eligible non-MAANGO
application per rolling hour). Screening errors are therefore expensive — this
file exists because one slipped through.

## The mistake worth not repeating

A batch pre-filter classified leads by **URL slug only**. It passed
`jobs.ashbyhq.com/incident/<uuid>/application` as US-eligible. The role was
**London, £65K**, and the location appeared only on the *post-submit*
confirmation page. Kevin has no UK work authorization, so the application was
dead on arrival.

Root cause: Ashby and Greenhouse both use a company-slug URL that encodes nothing
about the office. `job-boards.greenhouse.io/acme/jobs/123` is equally consistent
with Ohio and Singapore.

## Two-stage screen

**Stage 1 — slug pre-filter (cheap, catches obvious rejects only).**
Useful negative patterns observed in real lead dumps:

| Pattern | Rejects |
|---|---|
| `/Toronto-`, `/TORONTO-`, `-Ontario-`, `/London/`, `/zh-CN/`, `careers-canada` | non-US location |
| `New-Grad`, `new-college-grad`, `2027-Start` | needs a 2027 graduate, not May 2028 |
| `Current-Master-s`, `Current-PhD`, `Master-s--` | advanced degree required |

Also strip CDN/asset URLs harvested alongside real links: `cdn.greenhouse.io`,
`/api/images/`, `share_image`, `/logos/`.

**Stage 2 — read the actual listing before submitting. Non-negotiable.**
Cheapest reliable sources:
- Greenhouse: `https://boards-api.greenhouse.io/v1/boards/<board>/jobs/<id>?questions=true`
  returns `title`, `location.name`, and full `content`.
- Greenhouse embed tokens: follow `boards.greenhouse.io/embed/job_app?token=<t>`;
  the redirect resolves the real board and the `<title>` names company + role.
- Ashby: the rendered job page shows Location / Employment Type / Compensation.

Confirm from that text: **location**, graduation-window fit, degree level, and
any GPA floor.

## Kevin's gates (graduates May 2028, US citizen, GPA 3.236)

Reject before spending a submit:
- "New Grad" / "2027 Start" roles — they want a 2027 graduate.
- PhD- or Master's-only programs.
- Non-US postings (no work authorization outside the US).
- Any stated GPA floor above 3.236.

Accept: winter and full-time internships, not only summer.

## Verified-eligible examples from a real screen

Passing stage 2: Dropbox SWE Intern (Summer 2027), Coinbase SWE Intern,
Gallup SWE Intern Summer 2027, Viam SWE Intern, Talos SWE Intern (explicitly
requires Spring 2028 graduation), RF-SMART, Motorola R68388.

Rejected at stage 2 *after* passing the slug filter: ID.me Data Scientist
(MS required), ID.me Associate PM (new grad), True Anomaly (new grad),
SpaceX Starship (new grad), TD Bank (Toronto).
