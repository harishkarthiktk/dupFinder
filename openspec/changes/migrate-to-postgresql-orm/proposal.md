# Proposal: Migrate Database to PostgreSQL with SQLAlchemy ORM

## Summary
This change proposes migrating the dupFinder project's database backend from SQLite to PostgreSQL, while transitioning from SQLAlchemy Core to full ORM usage. The migration introduces a configurable `config.json` for database settings, enabling easy switching between PostgreSQL (default) and SQLite fallback. No data migration from existing SQLite databases is included; all scans will use a fresh PostgreSQL database. This enhances scalability and concurrency for larger file scans, aligning with project goals for performance on directories exceeding 10k files.

## Objectives
- Enable PostgreSQL as the primary database for better handling of concurrent operations in multiprocessing scans (e.g., main_mul.py).
- Adopt SQLAlchemy ORM for declarative models, improving maintainability and reducing boilerplate in database interactions.
- Introduce flexible configuration via `config.json` to support multiple database types without code changes.
- Maintain backward compatibility for SQLite via config, allowing users to opt-in for the legacy backend.
- Defer comprehensive testing to a follow-up change, focusing on functional migration first.

## Scope
- **In Scope**:
  - Update dependencies to include PostgreSQL driver (psycopg2-binary).
  - Create and integrate `config.json` for database connection parameters.
  - Refactor `utilities/database.py` to use ORM models (FileHash, ScanMetadata) and dynamic engine creation.
  - Update database functions (e.g., upsert_files, get_pending_files) to ORM sessions.
  - Modify `main.py` and `main_mul.py` to use refactored ORM-based calls, with multiprocessing-safe session handling.
  - Update documentation (README.md) for new setup and config usage.
  - Add indexes and pooling optimizations for PostgreSQL.
- **Out of Scope**:
  - Data migration scripts from SQLite to PostgreSQL.
  - New unit/integration tests (deferred).
  - Changes to HTML report generation unless ORM queries directly impact it.
  - External dependencies beyond Python packages.

## High-Level Impacts
- **Positive**:
  - Improved performance and concurrency for large-scale scans via PostgreSQL's robustness.
  - Cleaner, more Pythonic database code with ORM, easing future extensions (e.g., Analyzer part).
  - User flexibility with config.json and CLI overrides (e.g., --db-url).
- **Trade-offs**:
  - Requires local PostgreSQL setup (e.g., localhost:5432, database 'file_hashes'), increasing onboarding complexity vs. file-based SQLite.
  - ORM introduces slight overhead for simple operations but benefits complex queries.
  - No automatic schema migration; users start with fresh DBs.
- **Risks**:
  - Connection errors if PostgreSQL not running/configured; mitigated by error handling and SQLite fallback.
  - Multiprocessing session management pitfalls; addressed with per-process engines.
- **Affected Capabilities**:
  - Primary: database-management (backend switch, ORM adoption).
  - Secondary: scan-optimization (potential WAL-like concurrency in Postgres), multiprocessing-support (session handling).

## Sequencing
This change builds on existing specs without breaking current behavior. Implementation follows the tasks.md checklist, starting with dependencies and config, progressing to ORM refactoring, and ending with script/docs updates. Post-migration, a validation scan on a test directory confirms end-to-end functionality.

## Approval Criteria
- Proposal aligns with project constraints (cross-platform, no network calls).
- Spec deltas cover all modified requirements with scenarios.
- Tasks are verifiable and deliver incremental progress.
- Validation passes `openspec validate migrate-to-postgresql-orm --strict`.