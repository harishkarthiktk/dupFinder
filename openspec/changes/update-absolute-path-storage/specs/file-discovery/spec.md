## MODIFIED Requirements

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