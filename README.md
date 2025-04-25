# File Hash Scanner and Duplicate Finder

A tool for recursively scanning directories, calculating file hashes, storing the results in a SQLite database, and generating interactive HTML reports.

The purpose of the program is find duplicates; but the code is written in 2 major segments.
1) A hash scanner, that creates a sqlite db and html of the scanned folder.
2) An analyzer that reads the created sqlite db to find patterns of duplicates using the hashes generated.

> (1) has been completed and tested to work in Windows, Linux and MacOS.

> (2) development is in progress and the functionalities will be added natively soon; until then the generated html can be used to find duplicates and take actions.

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

Just Python 3.6+ with a few non standard libraries.

```bash
git clone https://github.com/harishkarthiktk/dupFinder.git
cd dupFinder
chmod +x main.py  # Make it executable (Unix/Linux/Mac)
pip install -r requirements.txt # Install the required libraries.
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
- above 2GB

## Database Schema

The SQLite database contains a single table `file_hashes` with the following columns:

- `id`: Integer primary key
- `filename`: File name without path
- `absolute_path`: Full file path (unique)
- `hash_value`: File hash as hexadecimal string
- `file_size`: File size in bytes
- `scan_date`: Scan timestamp


## Footnotes

Since the purpose of the program is to act as a CLI program, a major GUI is not in plan.
However, small elements for ease of use could be added down the line.

The HTML file generated could be large for browsers to handle without issues, and the table-data might cause browser slow down as well.
A workaround for that would be to directly query the sqlitedb created and get outputs.

Simple analysis queries will be added soon as an utility, and dedicated analysis system (2) is the primary work in progress.

## License

MIT License
