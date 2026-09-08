# Job-Agent Repo: Python Version Requirement

## `datetime.UTC` needs Python 3.11+

`submission_ledger.py` imports `from datetime import UTC, datetime, timedelta`. `datetime.UTC` was added in **Python 3.11**. Running the repo under macOS system Python (`/usr/bin/python3`, 3.9) fails at import time and takes down everything downstream of it:

```
ImportError: cannot import name 'UTC' from 'datetime'
  submission_ledger.py -> one_shot_submit.py -> production_operator.py
```

Because `production_operator.py` imports that chain at module load, **every** `production_operator.py live …` subcommand dies before argument parsing — including `--help`. The traceback names `datetime`, so it reads like a stdlib problem rather than an interpreter-version mismatch.

Do not "fix" this by rewriting the import or pinning to system Python. Run the repo with a 3.11+ interpreter.

Discover what is available before choosing one:

```bash
for p in python3.13 python3.12 python3.11 /opt/anaconda3/bin/python3 /opt/homebrew/bin/python3; do
  v=$(command -v $p 2>/dev/null) || continue
  echo "$v -> $($v --version 2>&1)"
done
```

On Kevin's machine this surfaced `/opt/homebrew/bin/python3` (3.14.6), `/opt/anaconda3/bin/python3` (3.13.9), and `~/.local/bin/python3.11` (3.11.16) — any of which satisfies the requirement.

Use the same interpreter for the offline test runner and the live CLI so import behaviour matches:

```bash
/opt/homebrew/bin/python3 run_offline_tests.py tests/test_workday_handler.py -q
/opt/homebrew/bin/python3 production_operator.py live deliver --help
```

Note a bare `python3` in a piped command can resolve to the 3.9 system binary even when a newer one is earlier in an interactive `PATH`. Prefer the absolute interpreter path in automation.

## Notifier requires the durable-outbox path

`notifier.py applied` intentionally refuses a direct send once an application is genuinely submitted:

```json
{"status": "blocked", "notification_state": "not_started",
 "reason": "A submitted notice requires verified portal evidence and the durable outbox",
 "next_action": "use production_operator.py live deliver for exact Discord read-back"}
```

This is a guard, not a bug — it exists so a "submitted" claim cannot be announced without portal evidence and an exact read-back. Route confirmed-submission notices through `production_operator.py live deliver` (which needs the 3.11+ interpreter above). `notifier.py maango` and other non-submission notices are unaffected.

Report confirmed submission and notification delivery as **separate states**. A verified ATS confirmation with an undelivered Discord notice is an accurate, reportable outcome — never restate it as a failed application, and never retry submission to fix a notification problem.
