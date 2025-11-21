# Refactoring Plan: Discovery-First Architecture

## Goal
Refactor [main.py](main.py) and [main_mul.py](main_mul.py) to implement a robust "Discovery First, Processing Second" architecture. This prevents memory explosions by avoiding holding all file data in RAM and enables resumable scans/incremental updates.

## User Review Required
> [!IMPORTANT]
> **Database Schema Change**: The `hash_value` column in the `file_hashes` table will be changed to `nullable=True`. This allows us to store files that have been found but not yet hashed.
> **Behavior Change**: The scan will now happen in two distinct phases:
> 1. **Discovery**: Rapidly finding files and updating the DB structure.
> 2. **Processing**: Calculating hashes for files that need it.

## Proposed Changes

### 1. Database Layer ([utilities/database.py](utilities/database.py))
- **Schema Update**: Modify [FileHash](utilities/database.py#L51) model to make `hash_value` nullable.
- **New Functions**:
    - `upsert_files(file_list)`: Efficiently insert new files or update existing ones (resetting hash if size/mtime changed).
    - `get_pending_files()`: Retrieve list of files where `hash_value` is NULL.
    - `update_file_hash(id, hash)`: Update the hash for a specific record.

### 2. Core Logic ([main.py](main.py) & [main_mul.py](main_mul.py))
Both scripts will follow this new flow:

#### Phase 1: Discovery (Fast)
- Walk the directory tree.
- Collect file metadata (Path, Size, Modified Time).
- **Batch Upsert** to DB:
    - If New -> Insert with `hash=NULL`.
    - If Exists & Modified -> Update Size/Date, set `hash=NULL`.
    - If Exists & Unchanged -> Skip (Preserve existing hash).

#### Phase 2: Processing (CPU Intensive)
- Query DB for all records where `hash=NULL`.
- **[main.py](main.py)**: Iterate sequentially, calculate hash, update DB.
- **[main_mul.py](main_mul.py)**: Use `multiprocessing` to calculate hashes in parallel, update DB in batches.

### 3. Cleanup
- Remove `colorama` from [requirements.txt](requirements.txt) (as requested previously).

