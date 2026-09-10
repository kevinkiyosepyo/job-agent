# Keeping the applied-ledger accurate during long batch runs

`~/Documents/job-agent/runtime/applied-ledger.json` is the canonical dedupe source
across runs. It only works if it is written **as** submissions confirm, not at the end.

Written after a session that submitted ~20 applications and let the ledger drift out of
sync three separate times.

## The failure mode

Confirming a submission and recording it are two different actions. Batch momentum makes
it easy to do the first repeatedly and the second never:

1. Scale AI and C3 AI were confirmed submitted, then left unlogged while the run moved
   on. A scheduled cron job firing in that window would have re-attempted both.
2. Schonfeld and two HP IQ roles were submitted and confirmed, and only discovered
   missing while logging an unrelated Dropbox application — the ledger read `13` when
   `16` had actually gone out.
3. The repo's `submission-ledger.sqlite3` held exactly **one** row and none of the
   session's real submissions. It is not authoritative for CDP/manually filed
   applications and must never be treated as complete history.

None of these produced an error. The ledger simply understated reality, and every
understatement is a duplicate-application risk.

## Rule: append immediately after each confirmation

The write belongs in the same step as the confirmation check, not in a batch at the end:

```
submit -> read explicit confirmation evidence -> append to ledger -> next posting
```

Append only on real evidence (confirmation text, reference/application id, or a
candidate-home entry), and record that evidence verbatim:

```python
d["applied"].append({
    "company": "...", "role": "...", "url": "...", "ats": "greenhouse",
    "submitted": "YYYY-MM-DD",
    "evidence": "Confirmation page: 'Thank you for applying! ...'",
})
```

## Rule: reconcile before reporting a total

Before stating "N applications submitted", print the ledger and count it. If the number
disagrees with what the run actually did, find the gap before reporting:

```python
print("TOTAL APPLIED:", len(d["applied"]))
for i, a in enumerate(d["applied"], 1):
    print(f"{i:2d}. {a['company']:20s} {a['role'][:50]}")
```

A total quoted from memory of the session is not a verified number. This reconciliation
is what surfaced the three missing entries above.

## Rule: log skips too, with the reason

The `skipped` array prevents re-triaging the same dead or ineligible postings every run.
Record enough detail that a future run does not need to re-derive the verdict:

- closed/filled postings — "no application form; page reads 'has been filled'"
- degree-gated — "requires MS/PhD; candidate holds BS"
- school-gated — "Waterloo co-op exclusive; requires a Waterloo email address"
- geography — "London/£-denominated" or "Canada — non-US"
- timing — "new-grad role targeting Dec 2026–2027 graduates; candidate graduates
  May 2028"
- policy — "MAANGO; requires explicit approval"

Batch-skip related postings in one entry when the reason is identical (for example a
whole feed of new-grad roles) rather than writing fifteen near-identical records.

## Rule: dedupe by normalized URL before applying

Widened discovery tiers re-surface older postings. Check the candidate URL against the
ledger before any form work:

```python
seen = {a["url"].rstrip("/") for a in ledger["applied"]}
seen |= {s.get("url", "").rstrip("/") for s in ledger.get("skipped", [])}
```

A posting already in `applied` is skipped silently; one in `skipped` is skipped with its
recorded reason.
