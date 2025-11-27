# Migration Plan: Switch from SQLite to PostgreSQL with SQLAlchemy ORM

This plan outlines the step-by-step migration of the dupFinder project's database from SQLite to PostgreSQL, while transitioning from SQLAlchemy Core (table-based operations) to full ORM (declarative models and sessions). The goal is to enable scalable, concurrent database operations suitable for larger scans, while maintaining backward compatibility where possible.

**Important Notes**:
- No data migration from existing SQLite databases. All scans will use a fresh PostgreSQL database.
- Tests are deferred for later implementation.
- Database configuration will be managed via a new `config.json` file in the root folder, allowing easy switching between database types (SQLite/PostgreSQL) and parameter customization.

The plan is structured as a checklist of tasks in logical execution order. Dependencies are noted. Each task includes:
- **Objective**: Clear goal.
- **Success Criteria**: How to verify completion.
- **Error Handling/Validation**: Steps to catch issues.
- **Dependencies**: Prior tasks required.

An AI agent (e.g., in Code mode) should execute tasks sequentially, updating this `plan.md` by marking checkboxes `[x]` upon completion and noting any issues in a sub-bullet.

## Prerequisites
- Ensure a local PostgreSQL server is running (default: localhost:5432).
- Create a database named `file_hashes` in PostgreSQL (user: postgres, password: set securely).
- Install/update dependencies as per Task 1.

## Task Checklist

- [ ] **Task 1: Update Dependencies for PostgreSQL Support**
  - **Objective**: Add PostgreSQL driver to `requirements.txt` to support the new backend.
  - **Steps**:
    - Add `psycopg2-binary==2.9.9` (PostgreSQL adapter for SQLAlchemy).
    - Keep existing `SQLAlchemy==2.0.40` and `tqdm==4.67.1`.
    - Run `pip install -r requirements.txt` to verify installation.
  - **Success Criteria**: No import errors when importing `psycopg2` in a Python shell.
  - **Error Handling/Validation**: If installation fails (e.g., missing build tools on Windows), suggest using `psycopg2-binary`. Validate by checking `pip list | grep psycopg2`.
  - **Dependencies**: None.
  - **Estimated Time**: 10 minutes.
  - **Agent Notes**: Update `requirements.txt` using `write_to_file` or `apply_diff`. Test import in a temporary script.

- [ ] **Task 2: Create config.json and Configure Database Connection for PostgreSQL**
  - **Objective**: Create a `config.json` file for database settings and modify `utilities/database.py` to load config from it, supporting PostgreSQL as the default backend.
  - **Steps**:
    - Create `config.json` in root with structure:
      ```
      {
        "database": {
          "type": "postgresql",
          "host": "localhost",
          "port": 5432,
          "user": "postgres",
          "password": "",
          "database": "file_hashes"
        }
      }
      ```
      For SQLite fallback: `"type": "sqlite"`, `"path": "./outputs/file_hashes.db"`.
    - In `utilities/database.py`, replace hard-coded `DB_CONFIG` with loading from `config.json` using `json.load`.
    - Implement dynamic engine creation based on config["database"]["type"], using `create_engine` with PostgreSQL URL (e.g., `postgresql://{user}:{password}@{host}:{port}/{database}`) or SQLite path.
    - Add connection pooling optimized for Postgres (e.g., `pool_size=20, max_overflow=30`); for SQLite, keep existing params.
    - Remove SQLite-specific args like `check_same_thread`.
    - Add a function to test connection (e.g., `ping` the engine).
    - Update `initialize_database` to load config, create the engine for the specified type, and handle initial connection. No migration logic needed.
    - Allow CLI args (e.g., `--db-url`) to override config if provided.
  - **Success Criteria**: Config loads correctly; engine creation succeeds without errors; a test query (e.g., `SELECT 1`) returns results for both DB types.
  - **Error Handling/Validation**: Catch `JSONDecodeError` for invalid config; `OperationalError` for connection issues. Validate by running `initialize_database` with config and checking logs.
  - **Dependencies**: Task 1.
  - **Estimated Time**: 40 minutes.
  - **Agent Notes**: Use `write_to_file` for `config.json`; `apply_diff` for `utilities/database.py`. Test with a mock config.

- [ ] **Task 3: Define ORM Models**
  - **Objective**: Replace SQLAlchemy Core tables with declarative ORM models in `utilities/database.py` for `file_hashes` and `scan_metadata`.
  - **Steps**:
    - Define `Base = declarative_base()` (already present).
    - Create `FileHash` model: `__tablename__ = 'file_hashes'`, with columns `id` (Integer PK), `filename` (String), `absolute_path` (String unique), `hash_value` (String nullable), `file_size` (BigInteger), `scan_date` (Float), `modified_time` (Float nullable).
    - Create `ScanMetadata` model: `__tablename__ = 'scan_metadata'`, with `id` (Integer PK), `last_scan_timestamp` (Float nullable).
    - Add indexes: `__table_args__ = (Index('ix_file_hashes_absolute_path', 'absolute_path'),)` for Postgres efficiency.
    - Use `Base.metadata.create_all(engine)` in `initialize_database` for schema creation.
  - **Success Criteria**: Models validate with `Base.metadata.create_all` on a test engine; no schema errors.
  - **Error Handling/Validation**: Handle `ProgrammingError` if columns conflict. Validate by inspecting models with `inspect(engine).get_table('file_hashes')`.
  - **Dependencies**: Task 2.
  - **Estimated Time**: 20 minutes.
  - **Agent Notes**: Refactor existing table definitions to models using `apply_diff`. Ensure backward compatibility for existing functions.

- [ ] **Task 4: Refactor Database Functions to Use ORM**
  - **Objective**: Update all functions in `utilities/database.py` (e.g., `upsert_files`, `get_pending_files`, `update_file_hash`, etc.) to use ORM sessions instead of Core tables.
  - **Steps**:
    - Replace `Table` definitions with model queries (e.g., `session.query(FileHash)`).
    - Use `session.add()`/`session.commit()` for inserts/updates.
    - Implement upsert logic with `session.merge()` for efficiency.
    - Update `get_session()` context manager to use ORM sessions.
    - Remove SQLite-specific code (e.g., raw `sqlite3.Connection` returns; use engine dispose).
    - Migrate legacy functions like `save_to_database` to ORM equivalents.
    - Handle batch operations with `session.bulk_save_objects()` or loops for safety.
  - **Success Criteria**: All functions execute without Core references.
  - **Error Handling/Validation**: Catch `IntegrityError` for unique violations. Validate by running a full scan on a test directory and checking DB contents via ORM queries.
  - **Dependencies**: Task 3.
  - **Estimated Time**: 60 minutes.
  - **Agent Notes**: Break into sub-diffs if needed (e.g., one per function group). Use `read_file` to verify before/after.

- [ ] **Task 5: Update Main Scripts to Use Refactored Database**
  - **Objective**: Modify `main.py` and `main_mul.py` to integrate ORM-based database calls, removing direct Core usage.
  - **Steps**:
    - Replace direct `Table`/`select`/`insert` in main scripts with calls to refactored functions (e.g., use `upsert_file_entry` ORM version).
    - Update imports to use ORM functions.
    - In `main_mul.py`, ensure multiprocessing-safe session handling (e.g., create sessions per process or use engine directly).
    - Remove SQLite pragmas (e.g., WAL mode).
    - Add arg for DB URL override (e.g., `--db-url`) to optionally bypass config.json.
    - Default to loading from `config.json`.
  - **Success Criteria**: Scripts run end-to-end with Postgres (via config.json), generating reports without errors.
  - **Error Handling/Validation**: Handle `SQLAlchemyError` for connection issues. Validate by scanning a small directory and querying Postgres for data.
  - **Dependencies**: Task 4.
  - **Estimated Time**: 40 minutes.
  - **Agent Notes**: Use `apply_diff` for both files. Test with `python main.py test_dir`.

- [ ] **Task 6: Documentation and Cleanup**
  - **Objective**: Update docs and clean up code for the new setup.
  - **Steps**:
    - Update `README.md` with instructions for setting up `config.json`, Postgres connection, and CLI overrides.
    - Add examples for `config.json` for both SQLite and PostgreSQL.
    - Remove deprecated SQLite-specific code/comments.
    - Update `utilities/html_generator.py` if DB queries change (e.g., to use ORM for report data).
  - **Success Criteria**: Docs reflect Postgres as primary with config.json usage; code is clean and commented.
  - **Error Handling/Validation**: N/A (review manually).
  - **Dependencies**: Task 5.
  - **Estimated Time**: 20 minutes.
  - **Agent Notes**: Use `apply_diff` for README. Verify by reading generated HTML report.

## Post-Execution
- Run a full end-to-end test: Configure `config.json` for Postgres, scan a directory, generate report.
- Total Estimated Time: ~3 hours.

This plan ensures a robust migration to a fresh PostgreSQL setup using configurable JSON.