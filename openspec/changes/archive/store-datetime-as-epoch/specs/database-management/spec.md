# Updated Database Management Specification

This spec updates the original database-management spec to reflect the change for storing `scan_date` as epoch timestamp (float) instead of string, with human-readable conversion for outputs.

## Requirements

### Requirement: SQLite Database Initialization
The system SHALL initialize a SQLite database at a configurable path, creating necessary tables and ensuring backward compatibility by adding missing columns if needed. The `scan_date` column SHALL be defined as Float (REAL) to store Unix epoch timestamps.

#### Scenario: First-Time Database Creation
- **WHEN** the database file does not exist and initialization is called
- **THEN** the directory is created if needed, tables 'file_hashes' and 'scan_metadata' are created with appropriate schema (scan_date as Float), and the connection is established

#### Scenario: Existing Database with String scan_date
- **WHEN** the database exists with `scan_date` as TEXT/STRING
- **THEN** a migration is triggered to convert string values to epoch floats (parse as '%Y-%m-%d %H:%M:%S', assume UTC, use `.timestamp()`), and the column type is updated implicitly via code handling

#### Scenario: Existing Database with Missing Columns
- **WHEN** the database exists but lacks the 'mtime' column
- **THEN** the column is added via ALTER TABLE without data loss

### Requirement: File Metadata Storage
The system SHALL store file metadata (filename, absolute_path, file_size, scan_date as epoch float, mtime as epoch float) and hash_value in the 'file_hashes' table, using upsert logic to insert new files or update existing ones. scan_date SHALL be set to `time.time()` on insert/update.

#### Scenario: New File Insertion
- **WHEN** a discovered file is not in the database
- **THEN** a new row is inserted with hash_value set to empty string for pending hashing, and scan_date as current epoch float

#### Scenario: Updated File Detection
- **WHEN** an existing file has changed size or mtime
- **THEN** the metadata is updated (including new epoch scan_date), and hash_value is reset to empty string to trigger re-hashing

### Requirement: Batch Hash Updates
The system SHALL support batch updates for hash values of multiple files to improve performance during scanning. scan_date remains unchanged during hash updates.

#### Scenario: Batch Hash Completion
- **WHEN** hashes for a batch of pending files are computed
- **THEN** all hashes are updated in a single transaction using individual UPDATE statements within the batch; scan_date is not modified

### Requirement: Pending Files Query
The system SHALL query for files that require hashing (where hash_value is NULL or empty). Queries MAY include scan_date for filtering by scan time (numeric comparisons).

#### Scenario: Retrieve Pending Files
- **WHEN** processing phase begins
- **THEN** a list of (id, absolute_path) tuples for files with empty hash_value is returned efficiently; optionally filter by scan_date > some epoch threshold

### Requirement: Scan Timestamp Management
The system SHALL maintain a last_scan_timestamp as epoch float in the 'scan_metadata' table to track scan history and enable optimization checks. scan_date in file_hashes SHALL use the same epoch format for consistency.

#### Scenario: Update Scan Timestamp
- **WHEN** a scan completes
- **THEN** the current Unix timestamp (`time.time()`) is inserted or updated in the scan_metadata table

#### Scenario: Retrieve Last Scan Time
- **WHEN** checking for unchanged files
- **THEN** the last_scan_timestamp is retrieved as float to compare against file mtimes (also float)

### Requirement: Time Conversion for Human Interfaces
The system SHALL convert epoch timestamps (scan_date, mtime) to human-readable local timezone strings when generating reports or other user-facing outputs.

#### Scenario: HTML Report Generation
- **WHEN** generating the HTML report
- **THEN** epoch scan_date is converted using `datetime.fromtimestamp(epoch).strftime('%Y-%m-%d %H:%M:%S %Z')` to display in local timezone (e.g., Asia/Calcutta)

#### Scenario: Direct Queries or Logs
- **WHEN** logging or returning data for user consumption
- **THEN** provide a helper function to convert epoch to local string; raw DB queries return floats for programmatic use

### Requirement: Concurrency Optimizations
The system SHALL configure the database for better concurrency, such as enabling WAL mode in multiprocessing scenarios. Epoch storage does not impact concurrency.

#### Scenario: WAL Mode Activation
- **WHEN** using the multiprocessing scanner
- **THEN** PRAGMA statements set journal_mode to WAL and synchronous to NORMAL for improved parallel access

## Schema Details
- **file_hashes Table**:
  - id: Integer (PK)
  - filename: String (nullable=False)
  - absolute_path: String (nullable=False, unique=True)
  - hash_value: String (nullable=True)
  - file_size: BigInteger (nullable=False)
  - scan_date: Float (nullable=False)  // Epoch timestamp
  - mtime: Float (nullable=True)  // Epoch timestamp

- **scan_metadata Table**:
  - id: Integer (PK)
  - last_scan_timestamp: Float (nullable=True)  // Epoch timestamp