# Change: Update Absolute Path Storage to Always Use Root-Relative Absolute Paths

## Why
The current implementation stores file paths in the database as `absolute_path` based on the provided scan path. If a relative path is given (e.g., `./docs`), the stored paths are relative to the script's current working directory (CWD), leading to inconsistencies across scans run from different directories. This prevents the database from serving as a reliable single source of truth for file locations, as path uniqueness and retrievability depend on the runtime CWD. To resolve this, all stored paths must always be full absolute paths starting from the root (e.g., `/home/user/docs/file.txt` on Linux or `C:\Users\user\docs\file.txt` on Windows), regardless of the input path type.

## What Changes
- Normalize the input scan path to absolute using `os.path.abspath()` before discovery.
- Ensure all discovered file paths (via `os.walk` or single file) are constructed as absolute paths.
- Update database upsert and storage logic to use these normalized absolute paths.
- No changes to hash calculation or reporting, but paths in generated HTML reports will now consistently be absolute.
- **BREAKING**: Existing database entries with relative paths will become invalid for lookups if the CWD changes. A one-time migration script may be needed for legacy data, but this proposal focuses on forward compatibility.

## Impact
- Affected specs: file-discovery (path normalization and discovery logic), database-management (storage of absolute_path).
- Affected code: 
  - [`main.py`](main.py): Path handling in discovery phase.
  - [`main_mul.py`](main_mul.py): Path handling in discovery phase.
  - [`utilities/database.py`](utilities/database.py): Upsert functions and schema documentation.
- Potential: Update tests in `tests/` to use absolute paths; minor impact on HTML reports in `utilities/html_generator.py`.
- Users: Scans from any CWD will produce consistent DB entries; relative paths in DB will need manual cleanup or migration.