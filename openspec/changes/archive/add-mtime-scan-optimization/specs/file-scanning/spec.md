## ADDED Requirements

### Requirement: File Modification Time Storage
The system SHALL store the modification time (mtime) of each scanned file in the database, represented as a Unix timestamp (float), alongside the file path, size, and hash.

#### Scenario: Store mtime during scan
- **WHEN** a file is scanned and hashed
- **THEN** the current mtime (obtained via os.path.getmtime) is inserted or updated in the database entry for that file path

#### Scenario: Backward compatibility for existing entries
- **WHEN** the database has existing entries without mtime
- **THEN** the mtime column is added with NULL default, and on first new scan, existing entries are not retroactively populated unless explicitly requested

### Requirement: Last Scan Timestamp Tracking
The system SHALL maintain a global last_scan_timestamp in the database, updated at the end of each scan run, to indicate the time of the most recent full scan.

#### Scenario: Update last_scan_timestamp post-scan
- **WHEN** a scan completes (single-threaded or multiprocessing)
- **THEN** the current timestamp is stored or updated in the database's metadata table

### Requirement: Conditional Hash Computation Based on mtime
During a scan, for each file path, the system SHALL check if an entry exists in the database and if the current file's mtime is not newer than the stored mtime from the last scan; if so, reuse the stored hash and metadata without recomputing the hash. If the mtime is newer or no entry exists, compute the hash and update the entry.

#### Scenario: Skip unchanged file
- **WHEN** scanning a file path that exists in the database with stored mtime <= current mtime and from the last scan
- **THEN** the hash computation is skipped, and the stored hash/size is used; progress is updated accordingly

#### Scenario: Re-hash modified file
- **WHEN** scanning a file with current mtime > stored mtime
- **THEN** the hash is recomputed, the entry is updated with new hash, size, and mtime

#### Scenario: First-time scan for new file
- **WHEN** no database entry exists for the file path
- **THEN** the hash is computed, and a new entry is inserted with current mtime, size, and hash

### Requirement: Cross-Mode Consistency
The mtime-based optimization SHALL be implemented consistently in both single-threaded (main.py) and multiprocessing (main_mul.py) scanning modes, ensuring thread-safe database operations in the multiprocessing version.

#### Scenario: Multiprocessing mtime check
- **WHEN** a worker process scans a file
- **THEN** it performs the mtime query and conditional hashing using a dedicated SQLAlchemy session, avoiding race conditions