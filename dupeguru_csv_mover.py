import os
import shutil
import csv
import logging
import hashlib
from pathlib import Path
from multiprocessing import Pool, cpu_count

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(processName)s] %(message)s',
    handlers=[
        logging.FileHandler("move_photos.log"),
        logging.StreamHandler()
    ]
)

def setup_directories(folder):
    """Ensure that the destination directory exists."""
    Path(folder).mkdir(parents=True, exist_ok=True)

def sha256sum(filepath, block_size=65536):
    """Calculate the SHA256 checksum of a file."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for block in iter(lambda: f.read(block_size), b''):
            h.update(block)
    return h.hexdigest()

def move_file(task):
    """Copy, verify, and delete source file for a single move task."""
    group_id, filename, src_folder, dst_folder = task
    src_path = Path(src_folder) / filename
    dst_path = Path(dst_folder) / filename

    try:
        if not src_path.exists():
            logging.warning(f"[{group_id}] SOURCE NOT FOUND: {src_path}")
            return

        setup_directories(dst_folder)

        if dst_path.exists():
            src_hash = sha256sum(src_path)
            dst_hash = sha256sum(dst_path)
            if src_hash == dst_hash:
                # Same file, remove source
                src_path.unlink()
                logging.info(f"[{group_id}] DUPLICATE (HASH MATCH): Removed {src_path}")
                return
            else:
                # Conflict: different files, rename and move
                base, ext = os.path.splitext(filename)
                renamed_filename = f"{base}_conflict{ext}"
                dst_path = Path(dst_folder) / renamed_filename
                logging.warning(f"[{group_id}] HASH MISMATCH: Renaming {filename} to {renamed_filename}")

        shutil.copy2(src_path, dst_path)
        src_size = src_path.stat().st_size
        dst_size = dst_path.stat().st_size

        if src_size == dst_size:
            src_path.unlink()
            logging.info(f"[{group_id}] MOVED: {src_path} -> {dst_path}")
        else:
            dst_path.unlink()
            logging.error(f"[{group_id}] SIZE MISMATCH, move aborted: {src_path} vs {dst_path}")

    except Exception as e:
        logging.exception(f"[{group_id}] ERROR moving {src_path} to {dst_path}: {e}")

def delete_empty_folders(folders):
    """Delete empty folders from the provided list, bottom-up."""
    for folder in sorted(folders, key=lambda f: len(str(f)), reverse=True):
        try:
            Path(folder).rmdir()
            logging.info(f"DELETED EMPTY FOLDER: {folder}")
        except OSError:
            pass  # Not empty or error

def main(csv_path):
    # Step 1: Read CSV and group by (Group ID, Filename)
    groups = {}
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            key = (row["Group ID"], row["Filename"])
            folder = row["Folder"]
            groups.setdefault(key, []).append(folder)

    # Step 2: Build move tasks with flipped source/destination logic
    tasks = []
    all_folders = set()
    for (group_id, filename), folders in groups.items():
        # Source = shortest path, Destination = longest path
        src = min(folders, key=lambda p: len(p))
        dst = max(folders, key=lambda p: len(p))
        if src != dst:
            tasks.append((group_id, filename, src, dst))
        all_folders.update(folders)

    # Step 3: Perform moves with multiprocessing
    num_workers = min(cpu_count(), len(tasks) or 1)
    logging.info(f"Starting move operations with {num_workers} workers (src=shortest, dst=longest)...")
    with Pool(processes=num_workers) as pool:
        pool.map(move_file, tasks)

    # Step 4: Post-operation cleanup of empty folders
    logging.info("Starting cleanup of empty folders...")
    delete_empty_folders(all_folders)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Move photos by Group ID (shortest->longest)")
    parser.add_argument("csv_file", help="Path to the CSV file")
    args = parser.parse_args()

    main(args.csv_file)
