# Metadata Collection Specification

## Requirements

### Requirement: File Metadata Extraction
The system SHALL extract essential metadata from each discovered file, including filename, absolute path, file size, modification time (mtime), and scan date.

#### Scenario: Successful Metadata Collection
- **WHEN** a file is discovered during scanning
- **THEN** the filename, absolute path, size in bytes, mtime as Unix timestamp, and current scan date are collected and associated with the file

#### Scenario: Error in Metadata Retrieval
- **WHEN** an error occurs while retrieving metadata (e.g., permission denied for size or mtime)
- **THEN** an error is logged, default values are used (e.g., size=-1, mtime=0.0), and the file is still included in the scan with available metadata

### Requirement: Cross-Platform Metadata Compatibility
The system SHALL retrieve metadata in a cross-platform compatible manner, using OS-agnostic functions to handle differences between Windows, Linux, and macOS.

#### Scenario: Path and Time Handling on Windows
- **WHEN** scanning on Windows with long paths or different time formats
- **THEN** absolute paths are correctly formed using os.path, and mtime is retrieved as float Unix timestamp

### Requirement: Scan Date Timestamping
The system SHALL record the scan date as a string in ISO-like format (YYYY-MM-DD HH:MM:SS) for each file at the time of discovery.

#### Scenario: Batch Scan Timestamp
- **WHEN** multiple files are discovered in a single scan
- **THEN** all files receive the same scan_date timestamp reflecting the start of the scan session