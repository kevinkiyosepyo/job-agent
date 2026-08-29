# Deterministic Job-Automation Pipeline

## Preferred architecture

`source adapters → source-health report → scanner/classifier → persistent queue → ATS preflight/handler → confirmation evidence → tracker API read-back → Discord reconciliation`

Use the deterministic repository commands under `~/Documents/job-agent` instead of rebuilding the pipeline ad hoc in prompts.

## Source and scanner rules

- Prefer official employer APIs/pages; snippets and aggregators are discovery hints only.
- Source collection must expose per-token failures and freshness state. Fail closed on partial errors, stale results, unknown timestamp freshness, malformed health reports, or contradictory aggregate/per-source health.
- Normalize URLs and deduplicate by exact official requisition URL first, then normalized company/role.
- A target level signal may live outside the title. A title like `2027 Software Engineer, Technology` can be eligible when official metadata says `Campus Undergraduate Internship Program`; do not accept it based on year alone.
- Preserve seniority, location, sponsorship, season, MAANGO, and tracker duplicate checks independently.

## Queue and worker rules

- Queue writes are idempotent by normalized official URL.
- Workers use leases, attempt counts, retry backoff, and stale-lease recovery so cron/manual overlap cannot duplicate actions.
- Manual states include pending question, CAPTCHA, and approval. Terminal failures must retain a reason.
- Job-ID-bound Discord controls may approve, reject, retry, or skip only the referenced queue item.

## ATS routing

- Greenhouse, Workday, Lever, and Oracle use their executable preflight/handler when available.
- Preflight is non-submitting: inventory controls, validate known answers, verify resume path/upload affordance, classify manual gates, and return a structured plan.
- Unsupported/custom forms remain leads until a handler or verified custom-form flow exists.

## Confirmation and reconciliation

Never mark `applied` from a click, spinner, disabled button, or navigation alone. Require normalized success text, confirmation URL/number, or exact candidate-home application status. Save a sanitized evidence artifact, append the eight-column tracker record, read it back, and reconcile the Discord result with the same queue job ID.

## Engineering mode versus operation mode

Autonomous build sprints must not submit applications, send notifications, mutate Workspace, or touch credentials/profile/resumes. Use fixtures and production-shaped dry runs. Real application operation starts only when preflight passes all safety gates.
