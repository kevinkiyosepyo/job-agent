# Tracker Writes, Read-Back, and Recovery

## Production rule

Use the official Google Sheets API for tracker mutations. Do not use raw canvas keystrokes or whole-sheet keyboard selection for production writes: Google Sheets can retain an unexpected range selection, and a cleanup key can affect far more than the intended test cell.

Canonical tracker helper: `~/Documents/job-agent/tracker.py`.

## Verified write pattern

1. Fetch the live tracker and run duplicate detection before writing.
2. Build exactly eight columns in the existing schema.
3. Append through the authenticated Sheets API.
4. Fetch fresh data and locate the exact appended row by a unique URL/marker plus company and role.
5. Report success only after read-back matches every expected value.
6. For integration checks, capture the original range, append a unique test marker, read it back, clear only the exact API-returned/found row range, and verify both marker absence and the original nonempty-row count.

The repository's `tracker.py integration-check` command implements a self-cleaning smoke path and restores the original rows even when verification fails. Prefer that over hand-built browser tests.

## Recovery after an accidental broad edit

Google Sheets version history is the validated recovery path:

1. Open **File → Version history → See version history**.
2. Expand the newest detailed version group.
3. Select the version immediately before the broad edit.
4. Preview that the original headers and application rows are present.
5. Restore that version.
6. Use the API to remove any isolated stray test cell if needed.
7. Re-fetch the tracker and verify expected row/status counts before resuming automation.

Never claim recovery from the visible grid alone; reload and verify through the API or the tracker helper.
