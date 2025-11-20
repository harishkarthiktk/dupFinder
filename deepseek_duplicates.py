import os
import hashlib
import shutil
import argparse
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

'''
# Basic usage (keep newest files, flatten structure):
python consolidator.py /path/to/source /path/to/target

# Keep oldest files and preserve structure:
python consolidator.py /path/to/source /path/to/target --preserve-oldest --preserve-structure

# Dry run (just show duplicates):
python consolidator.py /path/to/source /path/to/target --dry-run
'''

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('consolidator.log'),
        logging.StreamHandler()
    ]
)

def file_hash(filepath, chunk_size=8192):
    """Calculate MD5 hash of a file with error handling"""
    try:
        hasher = hashlib.md5()
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return filepath, hasher.hexdigest(), None
    except Exception as e:
        return filepath, None, str(e)

def find_duplicates(root_dir, max_workers=4):
    """Find duplicate files using size and MD5 hash with parallel processing"""
    files_by_size = {}
    files_by_hash = {}

    # First group by file size with progress
    logging.info("Scanning directory structure...")
    all_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            all_files.append(os.path.join(dirpath, filename))

    # Group by size with parallel processing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        size_results = []

        # Process files in batches for better progress tracking
        batch_size = 1000
        for i in tqdm(range(0, len(all_files), batch_size), 
                    desc="Indexing files", unit="files"):
            batch = all_files[i:i+batch_size]
            futures.append(executor.submit(process_batch, batch))

        for future in tqdm(as_completed(futures), desc="Processing files", 
                         unit="batch"):
            batch_result = future.result()
            for file_size, path in batch_result:
                if file_size not in files_by_size:
                    files_by_size[file_size] = []
                files_by_size[file_size].append(path)

    # Group by hash with parallel processing
    logging.info("Identifying duplicates...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        hash_futures = []
        for file_size, files in files_by_size.items():
            if len(files) > 1:
                for path in files:
                    hash_futures.append(executor.submit(file_hash, path))

        # Process hash results with progress
        for future in tqdm(as_completed(hash_futures), 
                         total=len(hash_futures),
                         desc="Hashing files", unit="file"):
            path, hash_value, error = future.result()
            if error:
                logging.error(f"Error hashing {path}: {error}")
                continue
            if hash_value not in files_by_hash:
                files_by_hash[hash_value] = []
            files_by_hash[hash_value].append(path)

    return [group for group in files_by_hash.values() if len(group) > 1]

def process_batch(batch):
    """Process a batch of files for size grouping"""
    results = []
    for path in batch:
        try:
            file_size = os.path.getsize(path)
            results.append((file_size, path))
        except OSError as e:
            logging.warning(f"Error processing {path}: {e}")
    return results

def consolidate_files(duplicate_groups, target_dir, 
                     preserve_oldest=True, preserve_structure=False,
                     max_workers=4):
    """Handle duplicates and move unique files with parallel processing"""
    kept_files = set()
    deleted_files = set()

    # Process duplicate groups with progress
    logging.info("Processing duplicate groups...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for group in duplicate_groups:
            futures.append(executor.submit(process_group, group, preserve_oldest))

        for future in tqdm(as_completed(futures), total=len(futures),
                          desc="Processing groups", unit="group"):
            keeper, to_delete = future.result()
            kept_files.add(keeper)
            deleted_files.update(to_delete)

    # Create target directory structure
    if preserve_structure:
        logging.info("Creating target directory structure...")
        dirs_created = set()
        for path in kept_files:
            rel_path = os.path.relpath(path, target_dir)
            target_path = os.path.join(target_dir, rel_path)
            target_dir_path = os.path.dirname(target_path)
            if target_dir_path not in dirs_created:
                os.makedirs(target_dir_path, exist_ok=True)
                dirs_created.add(target_dir_path)

    # Move files with parallel processing
    logging.info("Moving unique files...")
    move_operations = []
    for dirpath, _, filenames in os.walk(target_dir):
        for filename in filenames:
            src_path = os.path.join(dirpath, filename)
            if src_path in deleted_files:
                continue
            if src_path not in kept_files:
                move_operations.append((src_path, target_dir, preserve_structure))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(tqdm(executor.map(process_move, move_operations),
                total=len(move_operations),
                desc="Moving files", unit="file"))

    # Clean empty directories with parallel processing
    logging.info("Cleaning empty directories...")
    empty_dirs = []
    for root, dirs, _ in os.walk(target_dir, topdown=False):
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            if not os.listdir(dir_path):
                empty_dirs.append(dir_path)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(tqdm(executor.map(safe_rmdir, empty_dirs),
                total=len(empty_dirs),
                desc="Cleaning directories", unit="dir"))

def process_group(group, preserve_oldest):
    """Process a single duplicate group"""
    try:
        group.sort(key=lambda x: os.path.getmtime(x), reverse=not preserve_oldest)
        return group[0], group[1:]
    except Exception as e:
        logging.error(f"Error processing group: {e}")
        return None, []

def process_move(args):
    """Handle individual file move operation"""
    src_path, target_dir, preserve_structure = args
    try:
        if preserve_structure:
            rel_path = os.path.relpath(src_path, target_dir)
            dest_path = os.path.join(target_dir, rel_path)
        else:
            dest_path = os.path.join(target_dir, os.path.basename(src_path))

        # Handle filename conflicts
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(dest_path)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            dest_path = f"{base}_{counter}{ext}"

        shutil.move(src_path, dest_path)
    except Exception as e:
        logging.error(f"Error moving {src_path}: {e}")

def safe_rmdir(dir_path):
    """Safely remove directory"""
    try:
        os.rmdir(dir_path)
        logging.info(f"Removed empty directory: {dir_path}")
    except Exception as e:
        logging.warning(f"Failed to remove {dir_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Enhanced Duplicate File Consolidator')
    parser.add_argument('source', help='Source directory to scan')
    parser.add_argument('target', help='Target consolidation directory')
    parser.add_argument('--preserve-oldest', action='store_true',
                      help='Keep oldest file instead of newest')
    parser.add_argument('--preserve-structure', action='store_true',
                      help='Maintain folder structure in target directory')
    parser.add_argument('--dry-run', action='store_true',
                      help='Show what would happen without making changes')
    parser.add_argument('--workers', type=int, default=4,
                      help='Number of parallel workers (default: 4)')

    args = parser.parse_args()

    try:
        logging.info(f"Starting consolidation process (workers: {args.workers})")
        duplicates = find_duplicates(args.source, max_workers=args.workers)

        if args.dry_run:
            logging.info("\nDry run results (no changes made):")
            for group in duplicates:
                logging.info("\n".join(group))
                logging.info("---")
            return

        logging.info(f"Found {len(duplicates)} duplicate groups")
        consolidate_files(
            duplicates,
            args.target,
            preserve_oldest=args.preserve_oldest,
            preserve_structure=args.preserve_structure,
            max_workers=args.workers
        )

        logging.info("Consolidation complete. Final cleanup...")
        # Final empty directory cleanup in source
        empty_dirs = []
        for root, dirs, _ in os.walk(args.source, topdown=False):
            for dir in dirs:
                dir_path = os.path.join(root, dir)
                if not os.listdir(dir_path):
                    empty_dirs.append(dir_path)

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            list(tqdm(executor.map(safe_rmdir, empty_dirs),
                    total=len(empty_dirs),
                    desc="Final cleanup", unit="dir"))

        logging.info("Process completed successfully")

    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()