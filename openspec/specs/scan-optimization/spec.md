# Scan Optimization Specification

## Requirements

### Requirement: Unchanged File Skipping
The system SHALL skip hash recalculation for files that have not changed since the last scan, based on matching file size, stored modified_time, and comparison with the last scan timestamp.

#### Scenario: Unchanged File Detection
- **WHEN** a file's current size matches the stored size, stored modified_time is not null, and current modified_time <= stored modified_time, and stored modified_time >= last_scan_ts
- **THEN** the existing hash_value is retained, and the file is marked as skipped without re-hashing

#### Scenario: Changed File Re-hashing
- **WHEN** a file's size or modified_time indicates a change (e.g., current modified_time > stored modified_time)
- **THEN** the hash_value is reset to empty string, and the file is queued for re-hashing in the processing phase

### Requirement: Last Scan Timestamp Tracking
The system SHALL maintain and update a last_scan_timestamp upon scan completion to enable accurate change detection in future scans.

#### Scenario: Timestamp Update
- **WHEN** the scan processing and reporting phases complete
- **THEN** the current Unix timestamp is stored in the scan_metadata table, upserting if necessary

#### Scenario: Timestamp Retrieval
- **WHEN** checking for unchanged files during discovery
- **THEN** the last_scan_timestamp is queried to validate if stored modified_time is from the previous scan

### Requirement: Batch Metadata Processing
The system SHALL process file metadata in batches during discovery to optimize database interactions, using chunked queries for existing files.

#### Scenario: Batch Existing File Query
- **WHEN** syncing discovered files with the database
- **THEN** paths are chunked (e.g., 900 at a time) to query existing records without exceeding SQL variable limits, and inserts/updates are batched

### Requirement: Batch Hash Updates
The system SHALL update hash values in configurable batches (default 1000) to reduce database commit overhead during processing.

#### Scenario: Incremental Hash Batch Commit
- **WHEN** hashes are computed for pending files
- **THEN** every N (batch_size) successful hashes are committed to the database in a transaction, with remaining at the end

### Requirement: Database Concurrency Tuning
The system SHALL apply SQLite PRAGMA statements for better concurrency in multi-process scenarios, such as enabling WAL mode.

#### Scenario: WAL Mode in Multiprocessing
- **WHEN** the multiprocessing scanner initializes the database
- **THEN** journal_mode is set to WAL and synchronous to NORMAL to allow concurrent reads/writes across processes