# Unattended application controller

This controller uses the existing discovery, queue, preparation, Review,
one-shot submission and confirmation modules. It is not a general browser agent.
It never prompts for an answer: unsupported forms, missing material facts, and
rendered security/assessment gates are parked. Detection support for an ATS is
not evidence of automated filling/submission support.

## Current boundary

The connected autonomous backend supports only the learned, one-page Schonfeld
Greenhouse scope in `schonfeld_form.py`. Other discovered jobs are preserved as
unsupported, not declared closed or ineligible. Expanding the exact learned
scope requires canonical facts, option binding, upload byte verification,
complete Review provenance and connected confirmation tests before enablement.
This limitation means the current release is NOT a fully autonomous general
job-application service. Passing offline tests does not establish live ATS
readiness. No production service is enabled by installing these files.

## Safety and state

- Production profile is `~/Documents/job-agent/profile.json`; resolve its resume
  exactly and validate the bytes against the manifest and browser file object.
- Shared submission ledger: `~/Documents/job-agent/runtime/submission-ledger.sqlite3`.
  Immutable account/tenant/requisition fencing applies across job IDs/tokens.
- Unknown dispatched attempts block further submissions; they are never replayed.
  Confirmed successes impose a rolling hour without catch-up capacity.
- Queue claims and heartbeats use generation tokens. Security/unknown-fact gates
  before intent can park one candidate and allow an eligible alternative.
- Review expectations come from canonical facts, not the generated answers file.
  Actual values, option identities, provenance and resume bytes bind authorization.
- The existing approved normal-Chrome Unix worker is the only live transport.
  This program never starts a browser or accepts a security prompt. Health must
  verify that actual worker, not just an HTTP endpoint.
- STOP in the controller runtime, or SIGTERM/SIGINT, stops future stages.
  Do not terminate a pending browser request and then assume it was not sent.
- Confirmation is separate from notification. Delivery uses a durable deduplicated
  transaction, exact Discord read-back and a separate retry queue. Sheets are not
  read or written unless an operator explicitly requests tracker synchronization.
- The CLI registers old production intent journals before discovery. Missing,
  malformed or unresolved history prevents starting submissions. This only covers
  registered manifests: old ad-hoc scripts and manual applications must also be
  reconciled before claiming exclusive execution or comprehensive deduplication.

## Commands

Use the installed interpreter that has the repository dependencies:

    /opt/anaconda3/bin/python run_offline_tests.py
    /opt/anaconda3/bin/python autonomous_controller.py status --config /absolute/config.json
    /opt/anaconda3/bin/python autonomous_controller.py run-once --config /absolute/config.json
    /opt/anaconda3/bin/python autonomous_controller.py service --config /absolute/config.json

`production_enabled` defaults to false. `status` is read-only. `run-once` and
`service` require explicit production enablement and the canonical runtime path
`~/Documents/job-agent/runtime/autonomous-controller`. Service execution should
use a supervised process, not a chain of temporary background agent tasks.
Do not turn it on merely because the test command passed.

For production notifications, configure a Discord channel ID and the name of an
already supplied token environment variable; never put token values in JSON.
The service must actually receive that environment. A missing token leaves a
notification pending; it cannot change an application back into an unsubmitted job.

The offline test runner excludes three Chrome-launching tests and blocks external
network access. Their exclusion must be stated in any release report. Do not use
isolated Chrome fixtures as permission to operate Kevin's real browser.
