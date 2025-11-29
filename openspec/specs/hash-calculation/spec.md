# Hash Calculation Specification

## Requirements

### Requirement: File Hash Computation
The system SHALL compute cryptographic hashes for discovered files using a configurable algorithm (e.g., SHA-256, MD5) to enable duplicate detection based on content.

#### Scenario: Successful Hash Calculation
- **WHEN** a valid file path and algorithm are provided
- **THEN** the file is read in chunks, the hash is computed, and returned as a hexadecimal string

#### Scenario: Large File Handling
- **WHEN** a large file is hashed with a specified chunk size (default 8KB, configurable up to 4MB)
- **THEN** the file is read in memory-efficient chunks without loading the entire file into memory

### Requirement: Configurable Hash Algorithms
The system SHALL support multiple hash algorithms including MD5, SHA-1, and SHA-256, defaulting to SHA-256 for security.

#### Scenario: Algorithm Selection
- **WHEN** the user specifies an algorithm via command-line argument (e.g., -a md5)
- **THEN** the appropriate hashlib function is used to compute the hash

### Requirement: Error Handling in Hashing
The system SHALL handle I/O errors or permission issues during hash calculation gracefully, logging warnings and returning an error indicator instead of crashing.

#### Scenario: Unreadable File
- **WHEN** a file cannot be read due to permissions or I/O error
- **THEN** a warning is printed, and an error string (e.g., "ERROR: Permission denied") is returned as the hash value

### Requirement: Optimized Hashing in Multiprocessing
The system SHALL support optimized hashing with larger buffer sizes (e.g., 4MB) when using multiprocessing for performance on large directories.

#### Scenario: Multiprocessing Hash
- **WHEN** hashing in a multiprocessing context with custom chunk size
- **THEN** the buffer size is adjusted for efficiency, and the hash is computed in parallel across processes