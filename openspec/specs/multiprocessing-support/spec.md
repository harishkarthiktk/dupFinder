# Multiprocessing Support Specification

## Requirements

### Requirement: Parallel Hash Calculation
The system SHALL support parallel computation of file hashes using multiple processes to improve performance on large directories, utilizing ProcessPoolExecutor.

#### Scenario: Multiprocessing Initialization
- **WHEN** the multiprocessing scanner (main_mul.py) is invoked with a directory path
- **THEN** a ProcessPoolExecutor is created with a configurable number of workers (default: cpu_count()), and pending files are processed in parallel

#### Scenario: Single Process Fallback
- **WHEN** the number of processes is set to 1 or only one pending file exists
- **THEN** hashing proceeds sequentially without multiprocessing overhead

### Requirement: Configurable Process Count
The system SHALL allow users to specify the number of processes via command-line argument (-p), defaulting to the number of available CPU cores.

#### Scenario: Custom Process Count
- **WHEN** the user runs python main_mul.py /path -p 4
- **THEN** exactly 4 processes are used for hash calculations, regardless of CPU count

### Requirement: Optimized Hash Function for Parallelism
The system SHALL use an optimized hashing function with larger default chunk sizes (e.g., 4MB) in multiprocessing mode to reduce I/O overhead per process.

#### Scenario: Chunk Size Configuration
- **WHEN** a custom chunk size is specified (-c 8MB)
- **THEN** each process reads the file in 8MB chunks during hash computation for better performance on large files

### Requirement: Batch Processing in Parallel
The system SHALL collect hash results from parallel processes and update the database in configurable batches (default 1000) to balance memory usage and commit frequency.

#### Scenario: Incremental Batch Updates
- **WHEN** hash results are received from the executor
- **THEN** results are accumulated until the batch size is reached, then committed to the database, with remaining results committed at the end

### Requirement: Cross-Platform Multiprocessing Compatibility
The system SHALL ensure multiprocessing works on Windows by calling multiprocessing.freeze_support() and avoiding shared state issues.

#### Scenario: Windows Execution
- **WHEN** running on Windows
- **THEN** freeze_support() is called in if __name__ == "__main__", and processes are spawned correctly without pickling issues

### Requirement: Error Handling in Parallel Processing
The system SHALL handle exceptions from individual process tasks gracefully, logging errors and continuing with other files without aborting the entire scan.

#### Scenario: Failed Hash in One Process
- **WHEN** one process fails to hash a file (e.g., I/O error)
- **THEN** None is returned for that task, an error is printed, and the scan continues with remaining files