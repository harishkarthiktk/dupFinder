# Database Management Specification

## Purpose
The database management capability provides persistent storage and retrieval of file metadata, hashes, and scan information using SQLite. It ensures efficient initialization, upsert operations, batch updates, and concurrency optimizations for reliable duplicate file detection across scans.
## Requirements
### Requirement: SQLite Database Initialization
The system SHALL initialize a SQLite database at a configurable path, creating necessary tables and ensuring backward compatibility by adding missing columns if needed.

#### Scenario: First-Time Database Creation
- **WHEN** the database file does not exist and initialization is called
- **THEN** the directory is created if needed, tables 'file_hashes' and 'scan_metadata' are created with appropriate schema, and the connection is established

#### Scenario: Existing Database with Missing Columns
- **WHEN** the database exists but lacks the 'modified_time' column
- **THEN** the column is added via ALTER TABLE without data loss

### Requirement: File Metadata Storage
The system SHALL store file metadata (filename, absolute_path, file_size, scan_date as epoch float, modified_time as epoch float) and hash_value in the 'file_hashes' table, using upsert logic to insert new files or update existing ones. scan_date SHALL be set to current Unix timestamp (time.time()) on insert/update. The absolute_path SHALL always be a full root-relative absolute path (e.g., `/home/user/docs/file.txt` on Linux or `C:\Users\user\docs\file.txt` on Windows), ensuring consistency and uniqueness regardless of the scan's current working directory.

#### Scenario: New File Insertion
- **WHEN** a discovered file is not in the database
- **THEN** a new row is inserted with hash_value set to empty string for pending hashing, scan_date as current epoch timestamp, and absolute_path as the normalized full absolute path

#### Scenario: Updated File Detection
- **WHEN** an existing file has changed size or modified_time
- **THEN** the metadata is updated (including new epoch scan_date), hash_value is reset to empty string to trigger re-hashing, and absolute_path remains the full absolute path for lookup consistency

#### Scenario: Path Lookup Consistency
- **WHEN** querying or upserting by absolute_path from different working directories
- **THEN** the full root-relative absolute path ensures correct matching and avoids duplicates due to relative path variations

### Requirement: Batch Hash Updates
The system SHALL support batch updates for hash values of multiple files to improve performance during scanning.

#### Scenario: Batch Hash Completion
- **WHEN** hashes for a batch of pending files are computed
- **THEN** all hashes are updated in a single transaction using individual UPDATE statements within the batch

### Requirement: Pending Files Query
The system SHALL query for files that require hashing (where hash_value is NULL or empty).

#### Scenario: Retrieve Pending Files
- **WHEN** processing phase begins
- **THEN** a list of (id, absolute_path) tuples for files with empty hash_value is returned efficiently

### Requirement: Scan Timestamp Management
The system SHALL maintain a last_scan_timestamp in the 'scan_metadata' table to track scan history and enable optimization checks.

#### Scenario: Update Scan Timestamp
- **WHEN** a scan completes
- **THEN** the current Unix timestamp (time.time()) is inserted or updated in the scan_metadata table

#### Scenario: Retrieve Last Scan Time
- **WHEN** checking for unchanged files
- **THEN** the last_scan_timestamp is retrieved to compare against file modified_times

### Requirement: Concurrency Optimizations
The system SHALL configure the database for better concurrency, such as enabling WAL mode in multiprocessing scenarios.

#### Scenario: WAL Mode Activation
- **WHEN** using the multiprocessing scanner
- **THEN** PRAGMA statements set journal_mode to WAL and synchronous to NORMAL for improved parallel access

