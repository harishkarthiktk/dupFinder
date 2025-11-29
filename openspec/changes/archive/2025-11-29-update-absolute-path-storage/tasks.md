## 1. Update Path Handling in Discovery
- [x] In [`main.py`](main.py:26) and [`main_mul.py`](main_mul.py:54), normalize the input `path` to absolute using `os.path.abspath(path)` immediately after argument parsing and existence check.
- [x] In the discovery phase (lines ~88-104 in main.py and ~135-151 in main_mul.py), ensure `file_path = os.path.join(root, file)` uses the absolute base path, and verify all paths in `files_to_upsert` are absolute by calling `os.path.abspath(file_path)` if needed.
- [x] For single file input, ensure `path` is absolute before appending to `files_to_upsert`.

## 2. Update Database Storage Logic
- [x] In [`utilities/database.py`](utilities/database.py), update docstrings and comments in `upsert_file_entry` (lines 546-617) and `upsert_files` (lines 304-375) to emphasize that `absolute_path` must be a full root-relative absolute path.
- [x] Ensure uniqueness constraint on `absolute_path` remains, as absolute paths guarantee cross-session consistency.
- [x] No schema changes needed, but add validation in `initialize_database` (lines 53-127) to log a warning if any existing paths appear relative (optional for forward compatibility).

## 3. Update Affected Specs
- [x] Create delta spec for `file-discovery` under `changes/update-absolute-path-storage/specs/file-discovery/spec.md` with MODIFIED requirement for path handling.
- [x] Create delta spec for `database-management` under `changes/update-absolute-path-storage/specs/database-management/spec.md` with MODIFIED requirement for metadata storage.

## 4. Testing and Validation
- [x] Update integration tests in [`tests/test_integration.py`](tests/test_integration.py) to use absolute paths and verify stored `absolute_path` in DB is absolute.
- [x] Add unit tests in `tests/test_database.py` to confirm upsert with relative vs absolute inputs results in absolute storage.
- [x] Run full scan from different CWDs (e.g., via `execute_command` or manual) to verify DB consistency.
- [x] Validate the change with `openspec validate update-absolute-path-storage --strict`.

## 5. Documentation and Migration
- [x] Update README.md usage examples to recommend absolute paths, and note the change for existing DBs.
- [x] Provide a simple migration query or script suggestion in proposal.md for converting legacy relative paths to absolute (e.g., prepend stored CWD if known).