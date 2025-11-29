## MODIFIED Requirements

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