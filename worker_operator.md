# Approved Unix worker: one-page Greenhouse operator

Repository `/Users/kevinpoopz/Documents/job-agent`. This bridge now supports the **exact learned Schonfeld 8171772 guest form** through existing `production_operator.py live` stages. Other tenants keep their existing semantics. It never launches Chrome/a worker, opens a CDP WebSocket, navigates, uploads, types, sends notifications, or accesses Sheets. Preparation verifies an already filled form; mismatches require the parent to repair through the approved session. **Only `live submit` activates Submit, through the existing one-shot authorizer and intent journal.**

## Actual authority, not invented server persistence

`live review` routes the learned exact URL to `WorkerPage.read_greenhouse_client_bound_form()`. Canonical Review declares `source: live_client_bound_form`, `server_saved: false`, `submission_authorized: false`. This is explicit user-approved client-bound review, not a saved application or server Review. The old server-only method still refuses to pretend persistence exists.

The reader inventories every mapped field and all actual form inputs/selects/textareas, rejects unknown controls and validation/manual gates, expands required coverage when DOM/ARIA adds requirements, checks exact React-bound values (not search text), and hashes the **actual browser File** bound to the rendered resume slot. Filename alone is not enough. It searches the resume group's FileList and bounded React props/state ancestry; no uploads are repeated and no session-scoped CDP handles are reused. Missing retained File state is a real evidence blocker, not permission to manufacture a digest. Parent should inspect the real attachment state immediately after its approved upload if this occurs.

Telephone verification accepts exact local digits in controlled input props or an exact `phone`/`inputProps.id=phone` React ancestor's controlled `value`. It never declares a bare DOM value bound. Country code remains a separate, exact selected option. Education prefix selectors must each be unique. Populated optional answers must be explicitly approved too.

Review hashes commit to actual answer/choice/attachment state, profile/resume/approved-answer hashes, target/URL/company/role/requisition and provenance. Live observations must be at most 120 seconds old. One-page preparation/input bindings must remain unchanged and at most 600 seconds old at review/submit. Submit recomputes fresh Review and compares the exact approved hash, consumes one token, journals intent, then recomputes client state **inside the same DOM activation expression** before the one button click. Intent/uncertainty is never permission to replay or issue another authorization.

Page-only safety declares `observation_source: live_page_dom`, `activation_route: direct_dom`, and **`native_window_detected: null`**, not false. Native-window interception is inapplicable to direct page DOM activation. Hidden/disabled page controls and page-owned overlays/challenges still block. Offviewport fields can be read without scrolling; their unobscured state stays unknown rather than being falsely called obscured or unobscured.

## Accepted profile and answer contracts

Use the actual accepted application profile, not a fixture or a freshly invented identity. Hash its exact bytes in the manifest. Existing `resume_preflight.py` requires this shape (other profile fields remain supported):

```json
{
  "name": {"first": "<actual>", "last": "<actual>"},
  "contact": {"email": "<actual>", "phone": "<actual local digits>"},
  "education": {"university": "University of California, San Diego", "degree": "Bachelor of Science", "major": "Data Science", "gpa": 3.236, "expected_graduation": "2028"},
  "work_authorization": true,
  "requires_sponsorship": false,
  "application_facts": {
    "country": "United States +1",
    "location": "<independently accepted exact location label>",
    "education_start_month": "September",
    "education_start_year": "2024",
    "education_end_month": "May",
    "graduation_window": "Yes",
    "hispanic_latino": "No"
  },
  "resume": {
    "primary": "/Users/kevinpoopz/Downloads/Resume 2027 SWE.pdf",
    "required_application_filename": "Resume 2027 SWE.pdf",
    "do_not_use_for_applications": []
  }
}
```

Preserve the real profile's prohibited-file list and other facts; the example is a schema, not authorization to discard them. `verify_profile_answers()` independently compares every answer against this accepted profile at prepare, review and submit. Root canonical facts always win over `application_facts`; missing or conflicting facts block even if the answer file has a matching hash. `application_facts` is only for independently user-confirmed missing facts/tenant option labels—never mechanically copy a mutable agent answer file into it and call that independent approval. Preserve canonical `links.linkedin`, `links.website`, `gender`, and `race_ethnicity` when those optional answers are supplied. School/degree and the known Data Science → Other tenant dropdown fallback use narrow learned aliases. The selected file must exist, start with PDF magic, match the required basename, and not be prohibited. Explicitly approved GPA is **`"3.236"`**.

Answers are a plain semantic-key JSON object, not CSS keys, an envelope, or reconstructed browser evidence. All required keys:

```text
first_name last_name email country phone location resume
school degree discipline education_start_month education_start_year
education_end_month education_end_year gpa current_degree
work_authorization sponsorship_now sponsorship_future
```

`resume` is injected from the verified profile; an explicitly conflicting path fails. Optional keys: `linkedin`, `website`, `graduation_window`, `gender`, `hispanic_latino`, `race`. If populated on the live page, they must also appear in the approved answers. Text, year, phone and GPA answers are nonempty strings. React Select answer schema:

```json
{"search_text":"<approved search>","exact_option":"<real complete option label>","selected_option":"<rendered label, only if different>"}
```

Examples: country exact option `United States +1`, selected option `+1`; otherwise omit `selected_option` when displayed/full labels agree. `schonfeld_form.CONTROLS` and existing `tenant_field_maps.build_step_actions()` are the executable schema. Do not infer a real option from these examples; use observed approved labels.

## Manifest contract

`live_run_manifest.py` remains the closed schema; no new permissive live flags were added:

```text
schema_version: 1
mode: production_live
job_id: positive actual job integer
queue_id: original queue identifier
target: {id: CURRENT exact normal-Chrome target, url: exact original application URL}
identity: {company: Schonfeld, role: 2027 DMFI Technology Intern,
           requisition: P101884-2026-09-01, platform: greenhouse, tenant: schonfeld}
profile: {path: absolute accepted profile, sha256: exact lowercase SHA256, verified: true}
resume: {path: exact profile path, basename: Resume 2027 SWE.pdf,
         content_type: application/pdf, sha256: exact lowercase SHA256, verified: true}
manual_gate: {gates: [], maango: false, maango_approved: false, verified: true}
runtime_paths: {preparation, review, authorization_db, authorization_handoff,
                submit_journal, confirmation, transaction_db, status}
```

All runtime paths must be distinct absolute paths in the same existing run. Keep original job/queue/journal bindings. Do not set verified/manual-gate flags without fresh actual observation. Do not use the expired target from an earlier session. Do not delete/recreate any authority or intent file to make a run pass.

The role's requisition is not necessarily in the body. Supply the raw official public Greenhouse GET JSON as `--posting-evidence`. Dispatcher verifies its `id=8171772`, `absolute_url`, exact title/requisition and trimmed company name against the manifest while also requiring actual company/title in live HTML. Metadata stays separate from HTML; no visible requisition marker is inserted. Preserve this GET artifact unchanged; do not relabel cached DOM/React as server data.

## Runnable stage order (parent only, after live user approval)

From the repository, use the current **approved** socket, exact manifest and approved-answer file throughout. The currently proposed path is `/Users/kevinpoopz/.hermes/cache/random-job-20260904/browser.sock`; its existence/health does not itself authorize access. These commands are guidance; the offline engineering worker did not run them.

```sh
SOCKET=/Users/kevinpoopz/.hermes/cache/random-job-20260904/browser.sock
POSTING=/Users/kevinpoopz/.hermes/cache/random-job-20260904/official-posting.json
MANIFEST=/ABSOLUTE/PATH/actual-manifest.json
ANSWERS=/Users/kevinpoopz/.hermes/cache/random-job-20260904/approved-answers.json

python3 worker_operator.py --worker-socket "$SOCKET" --posting-evidence "$POSTING" live preflight --manifest "$MANIFEST" --enable-production-live
python3 worker_operator.py --worker-socket "$SOCKET" --posting-evidence "$POSTING" live prepare --manifest "$MANIFEST" --approved-answers "$ANSWERS" --step application --enable-production-live
python3 worker_operator.py --worker-socket "$SOCKET" --posting-evidence "$POSTING" live review --manifest "$MANIFEST" --approved-answers "$ANSWERS" --step application --enable-production-live
```

Inspect the value-free Review artifact and its exact source/hash. Only with the user's actual submit authorization:

```sh
python3 worker_operator.py --worker-socket "$SOCKET" --posting-evidence "$POSTING" live authorize --manifest "$MANIFEST" --actor '<actual operator>' --approve-review-hash '<exact reviewed SHA256>' --expires-in-seconds 300 --enable-production-live
python3 worker_operator.py --worker-socket "$SOCKET" --posting-evidence "$POSTING" live submit --manifest "$MANIFEST" --approved-answers "$ANSWERS" --step application --actor '<same actor>' --enable-production-live
python3 worker_operator.py --worker-socket "$SOCKET" live confirmation --manifest "$MANIFEST" --enable-production-live
python3 worker_operator.py --worker-socket "$SOCKET" live status --manifest "$MANIFEST" --enable-production-live
```

Repeat any additional `--required-question`/`--required-parser-repair` flags identically at review and submit. The learned form always inventories all known/actual required controls; omitting these flags never skips them. The inherited CDP HTTP-origin option is syntactically checked but unused by DI; leave it alone. No HTTP/CDP endpoint is opened.

## Guest confirmation and failure recovery

Inside the original journaled one-shot invocation, after the one attempted activation, the worker observes the **same target only**, with bounded read-only polling for up to 20 seconds. Learned routes come from `greenhouse_guest_confirmation.is_permitted_confirmation_url`: original URL, original `/confirmation` or `/thank_you`, or exact same-tenant `/thank_you`. It neither navigates nor follows sibling tabs.

The trusted caller writes value-free transition hashes to `runtime_paths.confirmation + '.transition.json'` (exclusive creation, mode 0600). Subsequent `live confirmation` may bind that receipt's exact target/URL only after validating the original journal, Review and transition. That connection permits fixed snapshot expressions only—no click/fill capability. The separate confirmation reader verifies real rendered success plus canonical provenance. Guest Candidate Home is **inapplicable**, never fabricated. A click/disabled button/pending state is not success; `live submit` may conservatively report uncertain even when the following explicit confirmation stage succeeds.

If a connection dies, route is unknown, state changes after capture, receipt cannot be written, or visible security gate appears: preserve the run and inspect without replay. Missing transition cannot be recreated from journal presence or a manually opened thank-you URL. `deliver`/delivery recovery are intentionally excluded; no Sheets/notifications are authorized here.

## Offline regression

```sh
python3 -m pytest tests/test_client_bound_review.py tests/test_schonfeld_client_dom.py tests/test_one_page_production.py tests/test_worker_guest_transition.py tests/test_worker_operator.py tests/test_schonfeld_worker_form.py -q
python3 /Users/kevinpoopz/.hermes/cache/delegation/worker_operator_offline_tests.py
git diff --check
```

The task-local runner denies TCP/DNS/live browser sockets and external/browser/secret subprocesses, permits only disposable synthetic Unix peers and `node -e` fixtures, and deselects the three known real-Chrome tests. These are engineering results, not evidence of a live application.
