# Implementation Tasks: Store Datetime as Epoch

These tasks outline the step-by-step implementation for the proposed change. Execute in Code mode.

## Prerequisites
- Existing database may need migration; handle in code.
- Use Python's `time` and `datetime` modules for epoch handling and local timezone conversion.
- Test on sample database with both old string and new float data.

## Task 1: Update Database Schema
- [x] In `utilities/database.py`, modify `initialize_database`:
  - Change `Column('scan_date', String, nullable=False)` to `Column('scan_date', Float, nullable=False)`.
  - Use `inspector` to detect if `scan_date` is TEXT/STRING; if so, trigger migration.
- [x] Ensure backward compatibility: Add/alter column if needed (though type change requires migration).

## Task 2: Implement Migration Function
- [x] Add `migrate_scan_date_to_epoch()` in `utilities/database.py`:
  - Connect to DB.
  - Query all rows: `SELECT id, scan_date FROM file_hashes WHERE scan_date IS NOT NULL AND typeof(scan_date) = 'text'`.
  - For each: Parse with `datetime.strptime(scan_date, '%Y-%m-%d %H:%M:%S')`, assume UTC, convert to epoch with `.timestamp()`.
  - UPDATE each row with new float value.
  - Commit in transaction; log errors for invalid dates (set to current time or NULL).
- [x] Call this in `initialize_database` if migration needed.
- [x] Add unit test for migration on sample data.

## Task 3: Update Storage Functions
- [x] In `utilities/database.py`:
  - `upsert_file_entry`: Set `scan_date = time.time()` (float) instead of `datetime.now().strftime(...)`.
  - `upsert_files`: Update to use epoch float for scan_date in inserts/updates.
  - `save_to_database` (legacy): Similarly update to epoch.
  - `update_last_scan_timestamp`: Already uses float; ensure consistency.
- [x] Import `import time` where needed.

## Task 4: Update Retrieval Functions
- [x] In `utilities/database.py`:
  - `get_all_records`: Return `scan_date` as float (already from DB).
  - `get_file_by_path`: Return `scan_date` as float.
  - No changes needed for queries; floats are returned natively.

## Task 5: Update HTML Report Generation
- [x] In `utilities/html_generator.py`:
  - Import `from datetime import datetime` and `import time`.
  - In `generate_html_report`:
    - For scan date display: `local_scan_date = datetime.fromtimestamp(records[0][4]).strftime('%Y-%m-%d %H:%M:%S %Z')` (uses local timezone).
    - If adding mtime display (future): Convert similarly.
  - Update table if including scan_date per row: Convert each to local string.
  - Handle None/0 values gracefully (e.g., 'Unknown').

## Task 6: Handle Timezone in Outputs
- [x] Use `datetime.fromtimestamp(epoch).astimezone()` for explicit local timezone (Asia/Calcutta or system default).
- [x] For reports: Format as '%Y-%m-%d %H:%M:%S %Z' to include timezone.
- [x] Test with different system timezones if possible.

## Task 7: Update Tests
- [x] In `tests/test_database.py`:
  - Add tests for epoch storage/retrieval.
  - Test migration: Create DB with string dates, run migration, verify floats.
  - Test local conversion in a mock report function.
- [x] Run full integration test: Scan, generate report, verify dates.

## Task 8: Documentation and Cleanup
- [x] Update `README.md` if CLI options affected (none).
- [x] Update `openspec/specs/database-management/spec.md` with new schema details.
- [x] Deprecate any string-based time handling.

## Verification
- Run `python main.py /path/to/dir` on existing DB: Migration runs, new entries use epoch.
- Generate report: Dates show in local human-readable format (e.g., "2025-11-22 19:06:05 IST").
- Query DB: `SELECT scan_date FROM file_hashes LIMIT 1` returns float (e.g., 1732300000.0).

Estimated Effort: 4-6 hours. Switch to Code mode after approval.