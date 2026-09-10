# Job Agent

**A bot that fills out job applications for you while you sleep, from creating accounts to submitting the application.**

![Job Agent filling a sanitized Greenhouse application end to end — verifying every field by read-back, submitting once, and confirming it landed — with no human in the loop](docs/demo.gif)

<sup>Real Chrome, real code path, fake company. The agent binds one exact page, fills each field, reads it back to prove it saved, hashes the resume, reconciles a Review, passes the policy check, issues itself a single-use token, submits exactly once, and reads the confirmation back. No human touched it. <a href="#try-it-without-touching-a-real-job-posting">Run it yourself.</a></sup>

Applying to internships means typing the same name, school, and phone number into hundreds of nearly identical forms. This project automates that typing. It finds job postings, opens the application form in a real Chrome browser, fills in the answers, verifies every one of them saved, and submits — on its own, around the clock.

---

## The one thing to understand

Most automation tools are built to go fast. This one is built to **refuse to do the wrong thing**.

A job application can only be submitted once. There is no undo button, no "recall message," no way to fix a typo after an employer receives it. So every part of this system is designed around a single rule:

> **If the program isn't certain, it stops. It never guesses.**

That's what lets it run unattended. It doesn't need a human watching because it refuses to act on anything it can't prove.

In the code you'll see this called *fail-closed*. It means the default answer is "no." A step only proceeds when it has proof it should. If something is ambiguous — the page changed, a field didn't save, a question is unfamiliar — the program halts and reports why, instead of pushing forward and hoping.

---

## How it works

The system moves a job through seven stages. Each stage has to prove it succeeded before the next one starts.

```
  1. FIND        Search public job boards for matching internships
       ↓
  2. PREPARE     Open the form in Chrome and fill in every field
       ↓
  3. REVIEW      Re-read the page and confirm every answer actually saved
       ↓
  4. AUTHORIZE   Policy check passes. Issues a one-time, expiring token.
       ↓
  5. SUBMIT      One single click. Cannot be repeated.
       ↓
  6. CONFIRM     Verify with the employer's portal that it truly arrived
       ↓
  7. DELIVER     Log it to the tracker and send a Discord notification
```

**Stage 3 is the important one.** After filling a field, the program doesn't trust that it worked. It reads the page back and compares what's actually there against what it meant to type. This is called *read-back verification*, and it's the reason the system catches a dropdown that silently reset or a file upload that didn't attach.

**Stage 4 is the safety gate.** Once the policy check passes (not a MAANGO company, no CAPTCHA, no assessment, no unknown questions), the system issues itself a token that works exactly once, expires in minutes, and is locked to that specific page. If anything changes between authorization and submission, the token stops working. It cannot authorize one application and accidentally submit a different one.

**Stage 5 can never repeat.** If the connection drops mid-click, the program is forbidden from clicking again. Instead it switches to inspection mode and looks for evidence of what happened. A double-submitted application looks careless to an employer; a delayed one doesn't.

---

## What a "verified" application means here

The program will not report an application as submitted just because the page said "Thank you for applying." A success message is easy to fake and easy to misread.

Instead it requires **two independent sources of proof**:

1. The confirmation page itself, validated by that specific ATS's handler
2. The employer's candidate portal showing exactly one matching application marked `submitted`

If those two disagree, or if the portal shows zero or multiple matches, the result is flagged for human review rather than recorded as a success.

---

## Things it will never do

These aren't limitations to work around — they're deliberate, and they're enforced in code:

| It won't | Why |
|---|---|
| Solve a CAPTCHA | Bypassing a human check is against site terms |
| Complete identity or email verification | That's the human proving it's them, not a bot |
| Take a timed assessment | The answers have to be the applicant's own |
| Invent an answer to an unfamiliar question | A wrong answer on an application is worse than no answer |
| Apply to Meta/Amazon/Apple/Netflix/Google/Microsoft automatically | Big-company applications route to manual review by policy |
| Submit twice | One-shot design, enforced by single-use tokens |
| Store your password | Credentials stay in the macOS Keychain, referenced but never copied |

When it hits one of these, it pauses, keeps the browser tab exactly where it is, notifies you, and waits. After you handle it manually, it picks up where it left off.

---

## Try it without touching a real job posting

The repo ships with fake job application pages so you can watch the whole thing run safely. Nothing here touches a real employer.

**Requires Python 3.11 or newer.** (The code uses `datetime.UTC`, which older versions don't have. macOS ships 3.9 by default, so point at a newer one explicitly.)

```bash
# 1. Confirm your setup is ready
python3 setup_diagnostics.py --skip-browser

# 2. Run the full test suite — 1274 tests, no network access
python3 run_offline_tests.py

# 3. Watch a complete fake application, start to finish
python3 production_operator.py local-demo \
  --resume runtime/sanitized-demo/Resume.pdf \
  --runtime-dir runtime/operator-demo \
  --output runtime/operator-demo/report.json \
  --approve-sanitized-submit
```

That last command launches a real Chrome browser against a local test page and runs all seven stages — including deliberately interrupting the submit step to prove the recovery logic doesn't double-click.

**Re-record the GIF at the top of this page** (submits the local fixture, nothing real):

```bash
python3 tools/record_demo.py --output docs/demo.gif
```

It drives `fixtures/demo_greenhouse_styled.html` through the same `MutableCDPPageAdapter` and `browser_actions` read-back contracts the production path uses, then asserts the fixture reports `submitted` — via the real `inspect_confirmation` read-back — before writing the file.

---

## Job boards it can handle

| Platform | Example employers |
|---|---|
| Greenhouse | Startups, mid-size tech |
| Workday | Large enterprises |
| Lever | Tech companies |
| Oracle Recruiting | Enterprise, government |
| Ashby | Modern startups |
| CGI / Njoyn | Consulting, government |

Each one has its own quirks — Workday hides fields behind multi-step wizards, Greenhouse rebuilds its form when React re-renders, Oracle returns blank pages if you read them too early. Each platform gets a dedicated handler that knows its specific behavior.

---

## Repo layout

```
job-agent/
├── README.md              ← you are here
├── docs/                  ← detailed technical documentation
│   ├── ARCHITECTURE.md      every module, what it does and why
│   ├── OPERATIONS.md        operator runbook and incident triage
│   ├── AUTONOMOUS-OPERATION.md   unattended controller setup
│   ├── WORKER-OPERATOR.md   client-bound review and submit
│   └── BUILD-LOG.md         development history
├── skills/                ← agent instructions for each ATS platform
├── tests/                 ← 1274 tests
├── fixtures/              ← fake job pages for safe testing
└── *.py                   ← the system itself
```

**New here?** Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) next — it walks through every file and explains what each piece is responsible for.

**Running it for real?** Read [`docs/OPERATIONS.md`](docs/OPERATIONS.md) for the command-by-command workflow and what to do when something breaks.

---

## Build your own: step-by-step

This walks you from an empty folder to the agent applying on your behalf. Every command here was run in a fresh clone on a clean machine before it was written down. Budget about 30 minutes for steps 1–5; step 6 depends on how many job boards you want to watch.

You need macOS, Google Chrome, and Python 3.11 or newer. No paid services.

### Step 1 — Clone and install

```bash
git clone https://github.com/kevinkiyosepyo/job-agent.git
cd job-agent

# Pick a Python 3.11+ interpreter. macOS ships 3.9, which will NOT work.
python3.13 --version   # or python3.12, python3.11, /opt/homebrew/bin/python3

python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Only two packages get installed — `websocket-client` for talking to Chrome, and `pytest`. Everything else is the Python standard library.

**Check it worked:**

```bash
python run_offline_tests.py
```

You should see `1273 passed, 1 skipped` (the skip is a check against the owner's personal profile, which you don't have yet). This suite runs with network access blocked, so it can't touch a real employer even by accident.

### Step 2 — Tell it who you are

The agent answers every form from one file: `profile.json`. It's gitignored, so your data stays on your machine.

```bash
cp profile.example.json profile.json
open -e profile.json      # or any editor
```

Fill in your real name, email, phone, school, and so on. The example shows every key the code reads. You can add more keys, but don't rename the ones that are there — `canonical_answers.py` looks them up by exact path.

The one you must get right is the resume:

```json
"resume": {
  "primary": "~/Documents/Your_Name_Resume.pdf"
}
```

That path has to point at a real PDF. The agent verifies the file's SHA-256 hash after every upload, so it needs the real bytes.

**Check it worked:**

```bash
python setup_diagnostics.py --skip-browser
```

Look for `"status": "ready"` at the top. If it says the profile is missing something, the message tells you the exact key.

### Step 3 — Watch it run against a fake job

Before letting it near anything real, see it work end to end on the bundled fake Greenhouse page. This is the same thing the GIF at the top shows.

```bash
python tools/record_demo.py --output /tmp/my-demo.gif
open /tmp/my-demo.gif
```

Chrome launches invisibly, the form fills in, the resume attaches, the fake application submits, and you get a GIF of the whole thing. The JSON it prints at the end should say `"submitted": "true"` and `"fields_verified": 9`.

If you want the heavier proof — the one that interrupts the submit mid-click to show it never double-fires:

```bash
python -m pytest tests/test_local_cdp_operator.py -q
```

### Step 4 — Find real jobs (no applying yet)

Discovery reads public job-board APIs. You give it board "tokens" — the slug in a company's careers URL. Copy it exactly; `andurilindustries` works and `anduril` returns a 404.

| If the careers page is… | the token is… |
|---|---|
| `job-boards.greenhouse.io/**andurilindustries**/jobs/...` | `--greenhouse andurilindustries` |
| `jobs.lever.co/**palantir**/...` | `--lever palantir` |
| `jobs.ashbyhq.com/**ramp**` | `--ashby ramp` |

```bash
python sources.py --greenhouse andurilindustries --lever palantir \
  --output candidates.json --report sources-report.json
```

This writes every active internship it found to `candidates.json` and a health report to `sources-report.json`. Exit code `0` means all boards answered and had fresh postings. `1` means a token failed (check the `failures` list in the output). `3` means a board came back empty or stale.

Now route them through the policy engine:

```bash
python orchestrator.py candidates.json \
  --source-report sources-report.json \
  --output orchestrator-report.json
```

Open `orchestrator-report.json` and look under `scan`. You'll see two lists:

- **`auto_apply_queue`** — jobs on a supported ATS that match your `preferences.target_roles`
- **`manual_only`** — jobs at Meta, Amazon, Apple, Netflix, Google, or Microsoft. The agent will never auto-apply to these; it flags them for you instead.

With the two boards above and the example profile, that's roughly 2,500 postings scanned and about 40 internship matches queued. Nothing has been submitted. This step only reads.

### Step 5 — Set up notifications and tracking (optional)

The agent can tell you when it applies and log every submission to a spreadsheet. Both are optional; skip this step and it'll just write to the local ledger at `runtime/applied-ledger.json`.

**Discord** — create a bot in the [Discord Developer Portal](https://discord.com/developers/applications), invite it to a server, then:

```bash
export DISCORD_BOT_TOKEN='your-bot-token'
export JOB_AGENT_DISCORD_TARGET='your-channel-id'
```

**Google Sheets** — make a blank sheet with these headers in row 1:

```
Company Name | Application Status | Role | Salary | Date Submitted | Link to Job Req | Rejection Reason | Notes
```

Then point the agent at it:

```bash
export JOB_AGENT_SHEET_ID='the-long-id-from-the-sheet-url'
```

The tracker authenticates through a Google OAuth token at `~/.hermes/google_token.json`. Verify the round trip with the self-cleaning smoke test — it appends one test row, reads it back, then removes it:

```bash
python tracker.py integration-check --tag setup-check
```

### Step 6 — Apply to one job, for real

Real applications go through the `production_operator.py live` command family. Every stage is a separate command, and each one re-verifies the page before acting. Read [`docs/OPERATIONS.md`](docs/OPERATIONS.md) for the full sequence; here's the shape of it:

1. Open Chrome with remote debugging on: `open -a "Google Chrome" --args --remote-debugging-port=9222`
2. Navigate to the job's application page yourself.
3. Write a **manifest** — a JSON file naming the exact page target, company, role, requisition, and where to put evidence. `live_run_manifest.py` documents every field.
4. Run the stages in order: `prepare` → `review` → `authorize` → `submit` → `confirmation` → `deliver`.

Each stage prints JSON. If any one says `human_required`, stop and look — that's the agent telling you it found something it couldn't prove. Nothing downstream will run until it's cleared.

**The autonomous version** — once you've done one by hand and trust it — is the unattended controller. Copy the example configs, set your approved boards, and flip `production_enabled` to `true`:

```bash
cp autonomous_config.example.json runtime/autonomous-controller/config.json
cp autonomous_sources.example.json runtime/autonomous-controller/sources.json
```

[`docs/AUTONOMOUS-OPERATION.md`](docs/AUTONOMOUS-OPERATION.md) covers the controller, pacing limits, and what it does when it hits a CAPTCHA at 3 a.m. (Short version: it holds the tab open, pings you, and waits.)

### Adding a job board it doesn't know yet

Every ATS the agent supports has a **handler** — a file that knows that platform's form structure. To add one:

1. Save a sanitized copy of the application page into `fixtures/` (strip any real data).
2. Write `yourplatform_handler.py` following the shape of [`lever_handler.py`](lever_handler.py) — it's the smallest one. A handler inventories fields, verifies the resume attached, and recognizes the confirmation page.
3. Register it in [`ats_registry.py`](ats_registry.py).
4. Add learned selectors to [`tenant_field_maps.py`](tenant_field_maps.py) — semantic keys like `first_name` mapped to one CSS selector each.
5. Write a test in `tests/` that drives your fixture through the handler and asserts `submission_enabled: false`.

If your handler can't prove a field saved, make it return a blocker rather than guess. That's the whole design.

---

## Privacy

Personal data never enters version control. Resumes, profiles, OAuth tokens, tracker exports, and generated run artifacts are all gitignored.

Evidence files that *are* saved deliberately strip the values out. A saved verification record proves *that* the phone-number field was filled and matched — it does not contain the phone number. Page HTML is replaced with a SHA-256 hash rather than stored.

---

## License

MIT
