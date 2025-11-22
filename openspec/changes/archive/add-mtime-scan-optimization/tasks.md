## 1. Database Schema Modifications
- [x] Update the database schema in utilities/database.py to include a new `mtime` column (float, Unix timestamp) for each file entry and a `last_scan_timestamp` column (float) in a new or existing metadata table to track the scan time per run.
- [x] Implement backward compatibility: Add columns with NULL defaults for existing databases; on first run with new schema, populate mtime for existing entries if possible.
- [x] Add functions to insert/update file metadata with mtime and update the global last_scan_timestamp after each scan.

## 2. Single-Threaded Scanner Updates (main.py)
- [x] Modify the file scanning loop in main.py to query the database for existing entries by path before computing hash.
- [x] If an entry exists and the current file's mtime <= stored mtime (or stored mtime is from the last scan), skip hash computation and reuse the stored hash/size.
- [x] If mtime is newer or no entry exists, compute hash, update/insert the entry with new mtime, and proceed.
- [x] After scanning completes, update the last_scan_timestamp in the database.

## 3. Multiprocessing Scanner Updates (main_mul.py)
- [x] Adapt the worker processes in main_mul.py to perform the mtime check and conditional hashing, similar to main.py, ensuring thread-safe database access (use SQLAlchemy sessions per process).
- [x] Modify the result aggregation to handle reused entries without re-hashing.
- [x] Ensure the global last_scan_timestamp is set post-scan, synchronized across processes.

## 4. Utility Module Enhancements
- [x] In utilities/hash_calculator.py, add a function to get file mtime using os.path.getmtime (cross-platform compatible).
- [x] In utilities/database.py, add query functions: get_file_by_path(path), is_file_unchanged(path, current_mtime), and update_last_scan_timestamp(timestamp).

## 5. Testing and Validation
- [x] Write unit tests in tests/ for mtime retrieval, database queries, and conditional hashing logic (mock file system and DB).
- [x] Add integration tests: Simulate a scan, modify a file's mtime, re-scan, and verify only changed files are hashed (measure time savings).
- [x] Test cross-platform mtime handling (Windows, Linux, macOS) with sample files.
- [x] Run full scans on sample directories before/after changes to benchmark efficiency.

## 6. Documentation and Cleanup
- [x] Update README.md with notes on the optimization and any new CLI flags if added (e.g., --skip-unchanged).
- [x] Ensure no regressions in HTML report generation or duplicate detection.
- [x] Run pylint, black, and pytest on the updated codebase.