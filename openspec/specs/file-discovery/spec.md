# File Discovery Specification

## Purpose
The file discovery capability handles recursive scanning of directories to identify files for hashing and metadata collection. It ensures cross-platform compatibility, error resilience, and normalization of paths to absolute formats for consistent storage and retrieval in the database.
## Requirements
### Requirement: Recursive Directory Scanning
The system SHALL recursively scan a given directory path to discover all files within it, including subdirectories.

#### Scenario: Successful Directory Scan
- **WHEN** a valid directory path is provided to the scanner
- **THEN** all files in the directory and its subdirectories are discovered and their paths collected

#### Scenario: Single File Input
- **WHEN** a single file path is provided instead of a directory
- **THEN** the file is discovered and treated as the only item to process

#### Scenario: Non-Existent Path
- **WHEN** a non-existent path is provided
- **THEN** an error message is displayed and the scan is aborted

### Requirement: Cross-Platform Path Handling
The system SHALL handle file paths in a cross-platform manner, supporting Windows, Linux, and macOS without OS-specific assumptions. All discovered file paths SHALL be normalized to full absolute paths from the root (e.g., `/home/user/docs/file.txt` on Linux or `C:\Users\user\docs\file.txt` on Windows) using `os.path.abspath()`, regardless of whether the input scan path is relative or absolute.

#### Scenario: Path Normalization
- **WHEN** paths with mixed separators (e.g., / and \) are provided
- **THEN** paths are normalized using `os.path.join` for construction and `os.path.abspath()` for ensuring root-relative absolute paths

#### Scenario: Relative Input Path
- **WHEN** a relative path (e.g., `./docs`) is provided as the scan target
- **THEN** it is converted to absolute using `os.path.abspath()` before discovery, and all resulting file paths in the database are full root-relative absolutes

#### Scenario: Absolute Input Path
- **WHEN** an absolute path (e.g., `/home/user/docs`) is provided
- **THEN** discovery uses the absolute path directly, ensuring all file paths stored are root-relative absolutes

### Requirement: Error Handling During Discovery
The system SHALL handle access errors (e.g., permission denied) gracefully during file discovery without crashing the entire scan.

#### Scenario: Permission Denied File
- **WHEN** a file in a subdirectory cannot be accessed due to permissions
- **THEN** an error is logged for that file, but scanning continues for other files

