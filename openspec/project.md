# Project Context

## Purpose
dupFinder is a tool designed to recursively scan directories, calculate file hashes, store results in a SQLite database, and generate interactive HTML reports to help identify duplicate files. The primary goal is to assist users in finding and managing duplicate files efficiently across various operating systems.

## Tech Stack
- Language: Python 3.6+
- Database: SQLite
- Dependencies: colorama==0.4.6 (colored terminal output), tqdm==4.67.1 (progress bars), SQLAlchemy==2.0.40 (database ORM)
- Reporting: HTML/CSS/JS (generated reports)

## Project Conventions

### Code Style
Follow PEP 8 guidelines for Python code. Use black for formatting, flake8 for linting, and isort for import sorting. Variable names should be descriptive (snake_case), classes in CamelCase, and functions in snake_case. Include docstrings for all public functions and classes using Google style.

### Architecture Patterns
The project uses a modular architecture with core scripts (main.py, main_mul.py) handling entry points and orchestration, and a utilities/ directory for separated concerns like hashing, database operations, and report generation. Follow single responsibility principle; multiprocessing is used for performance-critical tasks in main_mul.py.

### Testing Strategy
Use pytest for unit and integration tests. Aim for 80%+ code coverage. Test core functions in utilities/ (e.g., hash calculation, DB inserts) and end-to-end scanning/reporting. Mock file system operations for reproducibility. Run tests with `pytest` and include CI integration if expanded.

### Git Workflow
Use Git Flow: feature branches for new work (e.g., feature/analyzer), develop branch for integration, main for releases. Commit messages follow Conventional Commits (e.g., "feat: add multiprocessing support"). Pull requests require review; squash merges to main.

## Domain Context
The domain focuses on file system analysis for duplicates, emphasizing hash-based deduplication. Key concepts include recursive directory traversal, cryptographic hashing (SHA-256, MD5), metadata storage (path, size, hash), and visualization of duplicates via interactive reports. Cross-platform compatibility (Windows, Linux, macOS) is essential.

## Important Constraints
- Performance: Handle large directories efficiently; multiprocessing for scans >10k files.
- Cross-platform: Avoid OS-specific paths; use pathlib for portability.
- Security: Hashes are read-only; no file modifications without explicit user action.
- No external network calls; all operations local.
- Python 3.6+ minimum for compatibility.

## External Dependencies
- None; all dependencies are Python packages listed in requirements.txt.
- SQLite is built-in to Python; no additional setup required.
- Generated HTML reports are static and viewable in any modern browser.

## Specifications
The baseline specifications for core capabilities are defined in the following spec files:
- [file-discovery](specs/file-discovery/spec.md): Recursive scanning and path handling.
- [metadata-collection](specs/metadata-collection/spec.md): Extraction of file metadata including size and modified_time.
- [hash-calculation](specs/hash-calculation/spec.md): Computation of file hashes with configurable algorithms.
- [database-management](specs/database-management/spec.md): SQLite operations for storage and querying.
- [report-generation](specs/report-generation/spec.md): Interactive HTML report creation.
- [scan-optimization](specs/scan-optimization/spec.md): Skipping unchanged files and batch processing.
- [multiprocessing-support](specs/multiprocessing-support/spec.md): Parallel hash calculation for performance.
