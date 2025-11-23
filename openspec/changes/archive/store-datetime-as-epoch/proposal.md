# Change Proposal: Store Datetime as Epoch in Database

## Summary
This change proposes updating the database schema and related code to store the `scan_date` field as an epoch timestamp (float, Unix time in seconds) instead of a formatted string. This aligns with existing time fields like `mtime` and `last_scan_timestamp`, which are already stored as floats. For human interfaces (e.g., HTML reports), epoch timestamps will be converted to human-readable local timezone strings on output.

## Rationale
- **Consistency**: Currently, `scan_date` is stored as a string (e.g., '2025-11-22 13:36:05'), while `mtime` and `last_scan_timestamp` use epoch floats. Uniform epoch storage simplifies comparisons, sorting, and calculations across time fields.
- **Precision and Portability**: Epoch floats avoid timezone ambiguities and formatting variations. They are timezone-agnostic in storage but can be converted to local time (e.g., Asia/Calcutta, UTC+5:30) for display.
- **Query Efficiency**: Epoch allows efficient numeric queries (e.g., filtering scans within a time range) without string parsing.
- **Future-Proofing**: Easier integration with analysis tools or exports that expect numeric timestamps.
- **Minimal Impact**: No loss of readability in user-facing outputs; conversion happens at display time.

## Scope
- **Schema Change**: Alter `file_hashes.scan_date` from String to Float (REAL in SQLite).
- **Code Changes**:
  - Update storage functions (e.g., `upsert_file_entry`, `upsert_files`) to insert epoch floats using `time.time()`.
  - Update retrieval functions (e.g., `get_all_records`, `get_file_by_path`) to return epoch floats.
  - In `utilities/html_generator.py`, convert epoch to local human-readable string (e.g., using `datetime.fromtimestamp` with local timezone).
  - Handle `scan_metadata.last_scan_timestamp` consistently (already epoch).
- **No Changes Needed**:
  - `mtime` (already epoch).
  - Direct SQL queries by users (they can convert as needed).
- **Timezone Handling**: Use Python's `datetime` and `zoneinfo` (or `time.localtime`) to convert epoch to local timezone strings for display. Default to machine's local timezone (e.g., Asia/Calcutta).

## Impacts
- **Backward Compatibility**:
  - Existing databases: Run a migration script to convert string `scan_date` to epoch (parse with `datetime.strptime` and convert to timestamp).
  - New scans: Automatic epoch storage.
  - Queries: Update any code assuming string format (e.g., in reports).
- **Performance**: Negligible; float storage is efficient. Conversion on output is lightweight.
- **User Experience**: HTML reports show human-readable dates (e.g., "Nov 22, 2025 6:06 PM IST") instead of raw epochs or old strings.
- **Testing**: 
  - Unit tests for conversion accuracy across timezones.
  - Integration tests for migration on existing DBs.
  - Verify reports display correct local time.
- **Dependencies**: Add `zoneinfo` if using Python 3.9+ for timezone handling (or fallback to `pytz` if needed, but prefer stdlib).

## Migration Strategy
1. **Pre-Release**: Create a migration function in `utilities/database.py` (e.g., `migrate_scan_date_to_epoch`):
   - Query all rows where `scan_date` is string.
   - Parse each with `datetime.strptime(scan_date, '%Y-%m-%d %H:%M:%S')`.
   - Convert to epoch: `datetime_object.timestamp()`.
   - Update column (ALTER not needed; direct UPDATE).
   - Assume UTC for old strings (or detect timezone if possible).
2. **Schema Update**: In `initialize_database`, change `Column('scan_date', Float, nullable=False)`.
3. **Run Migration**: Call migration on init if column type mismatch detected (via `inspect(engine)`).
4. **Post-Migration**: Verify with sample queries; handle edge cases (invalid dates).

## Risks
- **Timezone Assumptions**: Old string dates lack timezone info; assume UTC to avoid errors. Document this.
- **Breaking Changes**: Any external scripts querying `scan_date` as string will break; recommend updating to handle floats.
- **SQLite Limitations**: No type enforcement; ensure code consistency.

## Alternatives Considered
- Keep string but standardize format (e.g., ISO 8601 with timezone): Less consistent with other fields; harder for numeric ops.
- Store as datetime object: SQLite doesn't natively support; epoch is simpler.
- No change: Misses consistency benefits.

## Approval
- **Status**: Proposed
- **Author**: Kilo Code (Architect Mode)
- **Date**: 2025-11-22