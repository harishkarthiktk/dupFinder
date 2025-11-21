# Project: dupFinder (File Hash Scanner and Duplicate Finder)

## Overview
dupFinder is a tool designed to recursively scan directories, calculate file hashes, store results in a SQLite database, and generate interactive HTML reports to help identify duplicate files.

## Key Components

### Core Application
- **`main.py`**: The primary entry point.
  - Scans directories recursively.
  - Calculates hashes (supports SHA-256, MD5, etc.).
  - Stores metadata (path, hash, size) in a SQLite database.
  - Generates an interactive HTML report.
- **`utilities/`**: Helper modules for hash calculation, database operations, and HTML generation.

### Scripts
- **`deepseek_duplicates.py`**: A standalone script for finding and consolidating duplicates.
  - Uses MD5 hashing and parallel processing (`ThreadPoolExecutor`).
  - Can move unique files to a target directory while preserving structure or flattening.
  - Supports "dry run" mode.
- **`dupeguru_csv_mover.py`**: Helper script to move files based on CSV exports from DupeGuru.

## Tech Stack
- **Language**: Python 3.6+
- **Database**: SQLite
- **Dependencies**: `tqdm` (progress bars), `colorama`, `SQLAlchemy`.
- **Reporting**: HTML/CSS/JS (generated reports).

## Current Status
- **Part 1 (Scanner)**: Complete. Scans, hashes, and reports. Works on Windows, Linux, macOS.
- **Part 2 (Analyzer)**: In progress. The goal is to add native analysis capabilities to find patterns of duplicates using the generated hashes. Currently, users can use the HTML report or direct SQL queries for analysis.

## Usage
```bash
# Basic Scan
python main.py /path/to/scan

# Consolidate Duplicates (Standalone Script)
python deepseek_duplicates.py /path/to/source /path/to/target --dry-run
```
