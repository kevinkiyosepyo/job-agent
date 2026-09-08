# Hourly new-job application pacing

Use this policy when Kevin asks for recurring hourly job discovery and application.

## Exact run contract

1. Begin each run by looking for newly posted or newly discovered active jobs on official employer/ATS sources. Prefer jobs that appeared since the prior run; use continuity and the durable queue/journal to exclude duplicates, already-seen URLs, prior attempts, closed listings, and confirmed submissions.
2. Verify the listing on the official page before any form mutation.
3. Apply to **exactly one successful job maximum per hourly run**. Stop immediately after the first verified confirmation. Never “make up” for prior zero-application hours by submitting more than one later.
4. If one candidate hits a recoverable browser, React, account, session, parser, or pipeline problem, debug it and keep trying. If that candidate has a genuine human/security gate or unknown material fact, preserve it and continue to another fresh eligible candidate when available.
5. A run may report `NO APPLICATION THIS HOUR` only after fresh sources and reasonable alternative candidates were actually checked. Report verified blockers honestly; never claim Applied without confirmation.
6. MAANGO employers remain notification-only unless the exact role receives separate approval.
7. One-shot submission safety still applies. If submit intent is consumed without confirmation, do not apply to a second job in that same run and do not replay Submit automatically.

The user’s emphasis is on both halves of the policy: discover jobs that newly appear, and submit **ONE—not multiple—per hour**.