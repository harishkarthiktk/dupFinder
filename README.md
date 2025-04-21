# File Hash Scanner

A tool for recursively scanning directories, calculating file hashes, storing the results in a SQLite database, and generating interactive HTML reports.

## Features

- Recursive directory scanning
- Multiple hash algorithm support (SHA-256, MD5, SHA-1, etc.)
- SQLite database storage
- Interactive HTML reports with:
  - Sortable columns
  - Text filtering for filenames and paths
  - File size range filtering
  - Human-readable file sizes

## Installation

No external dependencies are required! Just Python 3.6+ with standard libraries.

```bash
git clone https://github.com/yourusername/file-hash-scanner.git
cd file-hash-scanner
chmod +x main.py  # Make it executable (Unix/Linux/Mac)
```

## Usage

```bash
# Basic usage
python main.py /path/to/scan

# Specify hash algorithm
python main.py /path/to/scan -a md5

# Specify database and report paths
python main.py /path/to/scan -d my_hashes.db -r my_report.html
```

### Command Line Arguments

- `path`: Directory or file to scan (required)
- `-a, --algorithm`: Hash algorithm to use (default: sha256)
- `-d, --database`: SQLite database file path (default: file_hashes.db)
- `-r, --report`: HTML report file path (default: hash_report.html)

## HTML Report

The generated HTML report includes:

1. Statistics about the scan
2. Interactive filters:
   - Filename contains (text filter)
   - Path contains (text filter)
   - File size (dropdown with ranges)
3. Sortable table columns (click on column headers)

Size categories include:
- < 1MB
- 1-5MB
- 5-50MB
- 50-500MB
- 500MB-1GB
- 1-2GB
- > 2GB

## Database Schema

The SQLite database contains a single table `file_hashes` with the following columns:

- `id`: Integer primary key
- `filename`: File name without path
- `absolute_path`: Full file path (unique)
- `hash_value`: File hash as hexadecimal string
- `file_size`: File size in bytes
- `scan_date`: Scan timestamp

## License

MIT License