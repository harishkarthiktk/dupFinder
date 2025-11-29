# Database Management Spec Delta

This file defines the changes to the baseline [database-management spec](openspec/specs/database-management/spec.md) for the migrate-to-postgresql-orm change. It includes ADDED, MODIFIED, and REMOVED requirements to support PostgreSQL as the primary backend with SQLAlchemy ORM, while retaining SQLite as a configurable fallback. Changes focus on configurability, ORM adoption, and backend-agnostic operations, cross-referencing [file-discovery](openspec/specs/file-discovery/spec.md) for paths and [multiprocessing-support](openspec/specs/multiprocessing-support/spec.md) for concurrency.

## MODIFIED Requirements

### Requirement: Database Initialization
The system SHALL initialize a configurable database (PostgreSQL primary, SQLite fallback) at runtime, creating necessary tables via ORM models and ensuring schema compatibility by adding missing columns if needed.

#### Scenario: Configurable Database Creation
- **WHEN** initialization is called with config.json specifying "type": "postgresql"
- **THEN** a PostgreSQL engine is created using the provided URL (e.g., postgresql://postgres:@localhost:5432/file_hashes), tables are auto-created via Base.metadata.create_all, and connection pooling is enabled (pool_size=20, max_overflow=30)

#### Scenario: SQLite Fallback Initialization
- **WHEN** config.json specifies "type": "sqlite" with path "./outputs/file_hashes.db"
- **THEN** a SQLite engine is created with existing parameters (no check_same_thread), tables are created if missing, and backward compatibility alterations (e.g., add modified_time) are applied

#### Scenario: CLI Override
- **WHEN** --db-url arg is provided (e.g., postgresql://user:pass@host:port/db)
- **THEN** config.json is bypassed, and the engine uses the provided URL for initialization

### Requirement: File Metadata Storage
The system SHALL store file metadata (filename, absolute_path, file_size, scan_date as epoch float, modified_time as epoch float) and hash_value in the 'file_hashes' table using ORM models and upsert logic to insert new files or update existing ones. scan_date SHALL be set to current Unix timestamp (time.time()) on insert/update. Operations SHALL be backend-agnostic via sessions.

#### Scenario: ORM Upsert for New File
- **WHEN** a discovered file from file-discovery is not in the database
- **THEN** a FileHash ORM instance is created (hash_value='', scan_date=time.time()), merged via session.merge, and committed in a transaction

#### Scenario: Updated File Detection with ORM
- **WHEN** an existing file has changed size or modified_time (cross-ref: scan-optimization)
- **THEN** the FileHash instance is queried by absolute_path, updated (new scan_date, reset hash_value), and committed; unique constraint on absolute_path prevents duplicates

### Requirement: Batch Hash Updates
The system SHALL support batch updates for hash values of multiple files using ORM bulk operations to improve performance during scanning, compatible with both backends.

#### Scenario: ORM Batch Hash Completion
- **WHEN** hashes for a batch of pending files are computed (cross-ref: hash-calculation)
- **THEN** FileHash instances are bulk updated via session.bulk_update_mappings or individual merges in a single transaction, optimizing for PostgreSQL concurrency

### Requirement: Pending Files Query
The system SHALL query for files requiring hashing (where hash_value is NULL or empty) using ORM queries, returning (id, absolute_path) tuples efficiently with backend-specific indexes.

#### Scenario: ORM Pending Files Retrieval
- **WHEN** processing phase begins in multiprocessing-support
- **THEN** session.query(FileHash).filter(FileHash.hash_value.is_(None) | FileHash.hash_value == '').all() returns the list, leveraging ix_file_hashes_absolute_path index in PostgreSQL

### Requirement: Scan Timestamp Management
The system SHALL maintain a last_scan_timestamp in the 'scan_metadata' table using ORM to track scan history and enable optimization checks, backend-agnostic.

#### Scenario: ORM Update Scan Timestamp
- **WHEN** a scan completes
- **THEN** ScanMetadata instance is merged with current time.time() and committed

#### Scenario: ORM Retrieve Last Scan Time
- **WHEN** checking for unchanged files (cross-ref: scan-optimization)
- **THEN** session.query(ScanMetadata).first().last_scan_timestamp is returned for comparison

## ADDED Requirements

### Requirement: Configuration Loading for Database
The system SHALL load database configuration from config.json at initialization, supporting PostgreSQL and SQLite parameters, with error handling for invalid configs.

#### Scenario: Load PostgreSQL Config
- **WHEN** config.json contains valid PostgreSQL settings
- **THEN** parameters are parsed, engine created successfully; JSONDecodeError raised and logged if malformed

#### Scenario: Load SQLite Config
- **WHEN** config.json specifies SQLite path
- **THEN** engine uses the path; fallback if PostgreSQL connection fails (OperationalError)

### Requirement: ORM Model Definitions
The system SHALL define declarative ORM models (FileHash, ScanMetadata) extending Base, with appropriate columns, indexes, and relationships for backend portability.

#### Scenario: Model Schema Creation
- **WHEN** initialize_database calls Base.metadata.create_all
- **THEN** tables are created with columns (e.g., FileHash: id Integer PK, absolute_path String unique, etc.); indexes applied without errors

#### Scenario: Multiprocessing Session Safety
- **WHEN** multiple processes query/update (cross-ref: multiprocessing-support)
- **THEN** per-process sessions prevent conflicts; engine.dispose() called post-task

### Requirement: Connection Testing and Pooling
The system SHALL test database connections post-initialization and configure pooling for PostgreSQL to handle concurrent loads.

#### Scenario: Connection Ping
- **WHEN** engine created
- **THEN** engine.execute(text("SELECT 1")).scalar() succeeds; failures raise OperationalError with user-friendly message

#### Scenario: PostgreSQL Pooling
- **WHEN** high-concurrency scan (e.g., -p 8)
- **THEN** pool manages up to 20 connections + 30 overflow, reducing wait times vs. SQLite

## REMOVED Requirements

### Requirement: Concurrency Optimizations (SQLite-Specific)
The system SHALL NO LONGER configure SQLite-specific concurrency options like WAL mode, as PostgreSQL handles concurrency natively and ORM abstracts backend details.

#### Scenario: WAL Mode Activation (Removed)
- **WHEN** using the multiprocessing scanner
- **THEN** PRAGMA statements for journal_mode=WAL and synchronous=NORMAL are omitted; ORM sessions ensure safe parallel access across backends