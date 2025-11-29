# File Hash Scanner and Duplicate Finder

A tool for recursively scanning directories, calculating file hashes, storing the results in a database (PostgreSQL or SQLite), and generating interactive HTML reports.

The purpose of the program is find duplicates; but the code is written in 2 major segments.
1) A hash scanner, that creates a database and HTML report of the scanned folder.
2) An analyzer that reads the created database to find patterns of duplicates using the hashes generated.

> (1) has been completed and tested to work in Windows, Linux and MacOS.

> (2) development is in progress and the functionalities will be added natively soon; until then the generated html can be used to find duplicates and take actions.

## Features

- Recursive directory scanning
- Multiple hash algorithm support (SHA-256, MD5, SHA-1, etc.)
- Database storage (PostgreSQL or SQLite)
- Interactive HTML reports with:
  - Sortable columns
  - Text filtering for filenames and paths
  - File size range filtering
  - Human-readable file sizes
- Incremental scanning using scan_date and file modification times to skip re-hashing unchanged files on subsequent scans, improving performance on repeated scans

## Installation

Requires Python 3.6+ and either PostgreSQL (recommended) or SQLite.

### PostgreSQL Setup (Recommended)
1. Install PostgreSQL server (e.g., `sudo apt install postgresql` on Ubuntu, or download from postgresql.org)
2. Create a database: `createdb file_hashes`
3. Create a user (optional): `createuser --interactive --pwprompt postgres`

### SQLite Setup (Fallback)
No additional setup required - SQLite is included with Python.

### Install Dependencies
```bash
git clone https://github.com/harishkarthiktk/dupFinder.git
cd dupFinder
chmod +x main.py main_mul.py  # Make executable (Unix/Linux/Mac)
pip install -r requirements.txt
```

### Configuration
Create `config.json` in the project root:
```json
{
  "database": {
    "type": "postgresql",
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "your_password",
    "database": "file_hashes"
  }
}
```

For SQLite fallback:
```json
{
  "database": {
    "type": "sqlite",
    "path": "./outputs/file_hashes.db"
  }
}
```

## Running with Different Database Backends

### Using PostgreSQL (Recommended for Production)
1. Ensure PostgreSQL is running and configured as above
2. Use the default `config.json` or override with `--db-url`:
   ```bash
   python main.py /path/to/scan
   # or
   python main.py /path/to/scan --db-url postgresql://postgres:mypassword@localhost:5432/file_hashes
   ```

### Using SQLite (For Development/Testing)
1. No server setup required
2. Configure for SQLite in `config.json` or use CLI override:
   ```bash
   python main.py /path/to/scan --db-url sqlite:///outputs/file_hashes.db
   ```

### Switching Between Backends
- Edit `config.json` to change the `"type"` field
- Or use `--db-url` to override without changing config
- Existing data is not migrated automatically; re-scan directories for new backend

## Usage

**Note:** For consistent database entries across scans from different working directories, provide absolute paths (e.g., `/home/user/docs` or `C:\Users\user\docs`). Relative paths are automatically normalized to absolute, but existing databases with relative paths may require migration (see [Migration Notes](#migration-notes)).

**Performance Tip:** On repeated scans of the same directory, the tool now efficiently skips unchanged files using the `scan_date` timestamp, avoiding redundant hashing and significantly reducing scan time for large directories.

```bash
# Basic usage (single-threaded)
python main.py /path/to/scan

# Specify hash algorithm
python main.py /path/to/scan -a md5

# Override database URL
python main.py /path/to/scan --db-url sqlite:///my_hashes.db -r my_report.html

# Optimized usage (multiprocessing, recommended for large directories)
python main_mul.py /path/to/scan -p 4

# With custom options for multiprocessing
python main_mul.py /path/to/scan -a md5 --db-url postgresql://user:pass@localhost:5432/file_hashes -r ./outputs/hash_report.html -p 8 -c 8MB -b 2000
```

### Command Line Arguments (main.py)

- `path`: Directory or file to scan (required)
- `-a, --algorithm`: Hash algorithm to use (default: md5)
- `--db-url`: Database URL to override config.json (optional)
- `-r, --report`: HTML report file path (default: ./outputs/hash_report.html)
- `-v, --verbose`: Enable verbose output

### Advanced Command Line Arguments (main_mul.py)

- `path`: Directory or file to scan (required)
- `-a, --algorithm`: Hash algorithm to use (default: md5)
- `--db-url`: Database URL to override config.json (optional)
- `-r, --report`: HTML report file path (default: ./outputs/hash_report.html)
- `-p, --processes`: Number of processes to use (default: number of CPU cores)
- `-c, --chunk-size`: Read buffer chunk size in bytes (default: 4MB)
- `-b, --batch-size`: Number of files to process before database commit (default: 1000)
- `-v, --verbose`: Enable verbose output

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

The database (PostgreSQL or SQLite) contains two tables:

### file_hashes
- `id`: Integer primary key
- `filename`: File name without path
- `absolute_path`: Full file path (unique)
- `hash_value`: File hash as hexadecimal string
- `file_size`: File size in bytes
- `scan_date`: Scan timestamp (Unix epoch float)
- `modified_time`: File modification time (Unix timestamp, for optimization)

### scan_metadata
- `id`: Integer primary key
- `last_scan_timestamp`: Last scan timestamp (Unix epoch float)

## Footnotes

Since the purpose of the program is to act as a CLI program, a major GUI is not in plan.
However, small elements for ease of use could be added down the line.

The HTML file generated could be large for browsers to handle without issues, and the table-data might cause browser slow down as well.
A workaround for that would be to directly query the database created and get outputs.

Simple analysis queries will be added soon as an utility, and dedicated analysis system (2) is the primary work in progress.

## Migration Notes

### Database Migration (v2.0)
As of this version, the database backend has been migrated to support PostgreSQL with SQLAlchemy ORM. Existing SQLite databases are still compatible via config.json, but for new scans, PostgreSQL is recommended for better performance.

To migrate from SQLite to PostgreSQL:
1. Set up PostgreSQL as described in Installation
2. Update `config.json` to use PostgreSQL
3. Re-scan your directories (no automatic data migration is provided)

### Path Migration
If you have an existing database with relative paths, you can migrate them to absolute paths using a simple SQL query (assuming you know the original scan's working directory, e.g., `/original/cwd`):

```sql
UPDATE file_hashes
SET absolute_path = '/original/cwd/' || absolute_path
WHERE absolute_path NOT LIKE '/%' AND absolute_path NOT LIKE 'C:%';
```

Run this in your database (e.g., via `psql` for PostgreSQL or `sqlite3` for SQLite).

## Recent Changes

### v2.0 - Database Migration to PostgreSQL + ORM
- **Database Backend**: Migrated from SQLite-only to support PostgreSQL (recommended) and SQLite (fallback)
- **ORM Adoption**: Full transition to SQLAlchemy ORM for cleaner database code and better maintainability
- **Configuration**: Added `config.json` for flexible database configuration
- **Performance**: PostgreSQL provides better concurrency for multiprocessing scans
- **CLI Updates**: Added `--db-url` argument for database URL overrides
- **Backward Compatibility**: Existing SQLite databases remain compatible via config

## License

MIT License
