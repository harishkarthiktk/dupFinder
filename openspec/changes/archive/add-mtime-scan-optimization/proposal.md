# Change: Add mtime-based optimization for repeated file scans

## Why
Repeated scans of the same directories currently recalculate hashes for every file, leading to unnecessary computation and time overhead. By capturing and storing each file's modification time (mtime) during scans and comparing it against the last scan timestamp for that path, the tool can skip hashing unchanged files. This optimizes efficiency for incremental scans while ensuring modified files are detected and re-hashed.

## What Changes
- Extend the database schema to store file mtime and a global last_scan_timestamp per run.
- Before computing a file's hash, query the database for the file's path; if the current mtime is not newer than the stored mtime from the last scan, reuse the existing hash and metadata.
- Implement the mtime check logic in both the single-threaded (main.py) and multiprocessing (main_mul.py) versions.
- Update database insertion to always store the current mtime and update the last_scan_timestamp.
- No changes to the HTML report generation, as it relies on the existing hash data.

## Impact
- Affected capabilities: Introduces optimization to the core file scanning process; new spec delta for "file-scanning".
- Affected code: main.py, main_mul.py, utilities/database.py (schema and query modifications), utilities/hash_calculator.py (conditional hashing).
- Performance: Significant speedup for re-scans of large, mostly unchanged directories; minimal overhead for first-time scans.
- Compatibility: Backward-compatible with existing databases (add columns with defaults); no breaking changes to CLI or output formats.