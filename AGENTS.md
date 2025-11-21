# Project: dupFinder (File Hash Scanner and Duplicate Finder)

## Overview
dupFinder is a tool designed to recursively scan directories, calculate file hashes, store results in a SQLite database, and generate interactive HTML reports to help identify duplicate files.

## Key Components

### Core Application
- **`main.py`**: The single-threaded primary entry point.
  - Scans directories recursively.
  - Calculates hashes (supports SHA-256, MD5, etc.).
  - Stores metadata (path, hash, size) in a SQLite database.
  - Generates an interactive HTML report.
- **`main_mul.py`**: The optimized multiprocessing version for better performance on large scans.
  - Supports parallel hash calculation using multiple processes.
  - Additional options for process count, chunk size, and batch size.
- **`utilities/`**: Helper modules for hash calculation, database operations, and HTML generation.

## Tech Stack
- **Language**: Python 3.6+
- **Database**: SQLite
- **Dependencies**: `colorama==0.4.6` (colored terminal output), `tqdm==4.67.1` (progress bars), `SQLAlchemy==2.0.40` (database ORM).
- **Reporting**: HTML/CSS/JS (generated reports).

## Current Status
- **Part 1 (Scanner)**: Complete. Scans, hashes, and reports. Works on Windows, Linux, macOS.
- **Part 2 (Analyzer)**: In progress. The goal is to add native analysis capabilities to find patterns of duplicates using the generated hashes. Currently, users can use the HTML report or direct SQL queries for analysis.

## Usage
```bash
# Basic Scan (single-threaded)
python main.py /path/to/scan

# Optimized Scan (multiprocessing, recommended for large directories)
python main_mul.py /path/to/scan -p 4

# With custom options
python main_mul.py /path/to/scan -a md5 -d ./outputs/file_hashes.db -r ./outputs/hash_report.html -p 8 -c 8MB -b 2000
```
