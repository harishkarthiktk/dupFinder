import os
from pathlib import Path
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import hashlib
import logging
import sqlite3
import threading
import platform
from datetime import datetime
from typing import Optional, Tuple

# --- Configuration ---
HASH_ALGORITHM = "sha256"
CHUNK_SIZE = 8192
QUEUE_MAX_SIZE = 1000

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- Database Setup ---
def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS folder_scan (
            hash_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            filepath TEXT UNIQUE,
            hash_value TEXT,
            file_size INTEGER,
            scan_date TEXT
        )
    """)
    conn.commit()
    return conn


import platform
import sys
from pathlib import Path

# Normalize exclusion sets (mostly already sets)
EXCLUDED_EXTENSIONS = {
    '.py', '.pyc', '.tmp', '.log', '.swp', '.bak', '.dll', '.sys', '.ini', '.dat',
    '.ds_store', '.lnk', '.db', '.lock'
}
EXCLUDED_FILENAMES = {
    'thumbs.db', 'desktop.ini', '.ds_store'
}
EXCLUDED_DIR_NAMES = {
    '__pycache__', 'node_modules', 'system volume information',
    '$recycle.bin', '.git', '.svn', '.hg', '.cache', '.trash', '.local'
}

if platform.system() == 'Windows':
    EXCLUDED_ROOT_DIRS = {
        Path(p).resolve() for p in (
            'C:\\Windows', 'C:\\Program Files', 'C:\\Program Files (x86)',
            'C:\\$Recycle.Bin', 'C:\\ProgramData', 'C:\\System Volume Information'
        )
    }
elif platform.system() == 'Linux':
    EXCLUDED_ROOT_DIRS = { Path(p).resolve() for p in (
        '/proc', '/sys', '/dev', '/run', '/var/lib', '/var/run', '/boot', '/tmp'
    )}
elif platform.system() == 'Darwin':  # macOS
    EXCLUDED_ROOT_DIRS = { Path(p).resolve() for p in (
        '/System', '/Volumes', '/dev', '/private', '/usr', '/bin', '/sbin', '/tmp', '/var'
    )}
else:
    EXCLUDED_ROOT_DIRS = set()

def is_hidden(file_path: Path) -> bool:
    # Check if any part of the path starts with '.'
    return any(part.startswith('.') for part in file_path.parts)

def should_exclude(file_path: Path) -> bool:
    # Resolve path once, to normalize
    try:
        file_path = file_path.resolve()
    except Exception:
        # If resolving fails (broken symlink etc), just use as-is
        pass

    # Fast hidden check
    if is_hidden(file_path):
        return True

    # Extension in excluded (suffix always lowercased)
    if file_path.suffix.lower() in EXCLUDED_EXTENSIONS:
        return True

    # Filename check (lowercase)
    if file_path.name.lower() in EXCLUDED_FILENAMES:
        return True

    # Directory exclusion check: only check parents/folders, skip filename (last part)
    # Lowercase comparison for robustness
    if any(part.lower() in EXCLUDED_DIR_NAMES for part in file_path.parts[:-1]):
        return True

    # Check if path is under any excluded root dir
    for excluded_root in EXCLUDED_ROOT_DIRS:
        try:
            # Python 3.9+ -- fast and reliable
            if file_path.is_relative_to(excluded_root):
                return True
        except AttributeError:
            # fallback pre-3.9, slower; compare resolved strings
            if str(file_path).startswith(str(excluded_root)):
                return True

    return False

# --- File Hashing ---
def calculate_file_hash(file_path: str, algorithm: str = HASH_ALGORITHM) -> Optional[str]:
    try:
        hash_func = getattr(hashlib, algorithm)()
    except AttributeError:
        logging.error(f"Unsupported hash algorithm: {algorithm}")
        return None

    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    except (IOError, PermissionError) as e:
        logging.warning(f"Cannot read file {file_path}: {e}")
        return None

# --- File Processing Worker ---
def process_file(file_path: Path) -> Optional[Tuple[str, str, str, int, str]]:
    scan_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hash_value = calculate_file_hash(str(file_path))
    if hash_value is None:
        return None

    try:
        file_size = os.path.getsize(file_path)
    except (IOError, OSError) as e:
        logging.warning(f"Cannot get size of file {file_path}: {e}")
        return None

    return (file_path.name, str(file_path), hash_value, file_size, scan_date)

# --- DB Writer Thread ---
def db_writer(q: queue.Queue, conn: sqlite3.Connection, stop_signal: threading.Event):
    cursor = conn.cursor()
    while not stop_signal.is_set() or not q.empty():
        try:
            record = q.get(timeout=1)
            try:
                cursor.execute("""
                    INSERT INTO folder_scan (filename, filepath, hash_value, file_size, scan_date)
                    VALUES (?, ?, ?, ?, ?)
                """, record)
                conn.commit()
                logging.info(f"Inserted: {record[0]}")
            except sqlite3.IntegrityError:
                logging.warning(f"Skipped duplicate file: {record[1]}")
            q.task_done()
        except queue.Empty:
            continue
    conn.close()

# --- Main Scanner ---
import os
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed

def scan_directory(directory: str, q: queue.Queue):
    # Use os.scandir() for efficient directory scanning and file exclusion
    with ThreadPoolExecutor() as executor:
        future_to_path = {}

        # Generator to iterate over files in the directory
        def scan_files(directory: str):
            try:
                for entry in os.scandir(directory):
                    file_path = Path(entry.path)  # Convert to Path object
                    if entry.is_file() and not should_exclude(file_path):
                        yield file_path  # Yield Path objects
                    elif entry.is_dir():
                        # Recurse into subdirectories if needed
                        yield from scan_files(entry.path)
            except PermissionError as e:
                print(f"PermissionError: {e} - Skipping directory {directory}")
            except Exception as e:
                print(f"Unexpected error: {e} - Skipping directory {directory}")

        # Submit tasks for each valid file
        for file_path in scan_files(directory):
            future = executor.submit(process_file, file_path)  # Pass Path object to process_file
            future_to_path[future] = file_path

        # Process results as they complete
        for future in as_completed(future_to_path):
            result = future.result()
            if result:
                q.put(result)




# --- Main Entry Point ---
def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <directory_path>")
        sys.exit(1)

    directory_path = sys.argv[1]
    if not os.path.isdir(directory_path):
        print(f"Error: '{directory_path}' is not a valid directory.")
        sys.exit(1)

    db_path = os.path.join(os.path.dirname(__file__), "folder_scan.db")
    conn = init_db(db_path)

    q = queue.Queue(maxsize=QUEUE_MAX_SIZE)
    stop_signal = threading.Event()

    writer_thread = threading.Thread(target=db_writer, args=(q, conn, stop_signal))
    writer_thread.start()

    logging.info(f"Starting scan of directory: {directory_path}")
    scan_directory(directory_path, q)

    # Wait for all items to be processed
    q.join()
    stop_signal.set()
    writer_thread.join()
    logging.info("Scan complete.")

if __name__ == "__main__":
    main()
