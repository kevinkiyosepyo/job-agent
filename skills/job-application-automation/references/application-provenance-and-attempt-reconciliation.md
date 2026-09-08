# Application Provenance and Attempt Reconciliation

Use this when Kevin asks who supplied a job, whether an application was autonomous, or why an earlier attempt failed despite a later submission.

## Evidence hierarchy

1. The initiating user, cron, or monitor message containing the exact listing URL or requisition.
2. The execution session around the first browser mutation for that attempt.
3. Verified confirmation, tracker read-back, and delivered notification for the final state.

A notifier post or tracker row proves a resulting state, not who initiated the application. Never infer provenance from the submission timestamp or the channel where the success notification appeared.

## Required reconstruction

1. Normalize the exact company, role, requisition, and listing URL.
2. Search session history for the exact requisition/URL.
3. Starting from the confirmation or blocker, scroll backward to the initiating user/cron message.
4. Classify the trigger explicitly: `user_provided_link`, `autonomous_scan`, `scheduled_monitor`, or `manual_follow_up`.
5. Keep separate attempts separate. Report each trigger, blocker, and terminal state in chronological order.
6. If a scheduled scan failed but a later user-provided attempt succeeded, say both facts. Do not answer the later success as if it were autonomous, and do not describe the application as unsuccessful overall.

## Trade Desk example

For The Trade Desk requisition `5187605007`, a scheduled scan first found the role but could not expose the embedded Greenhouse controls. A later user message supplied the exact careers URL, after which the application was completed and explicitly confirmed. Correct provenance: the successful application was user-triggered; the earlier scheduled scan was a separate blocked attempt.

## Response pattern

- Lead source: who or what introduced the exact listing.
- Attempt timeline: any distinct blocked and successful attempts.
- Final state: only the latest state backed by confirmation/tracker evidence.
