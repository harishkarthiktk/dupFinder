#!/usr/bin/env python3
"""
File Hash Scanner - Main Entry Point (Multiprocessing)

This script provides a command line interface for scanning files,
calculating their hashes in parallel, storing them in SQLite, and generating HTML reports.
"""

import argparse
import os
import sys
import time
from tqdm import tqdm
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

# Custom Module Imports
from utilities.hash_calculator import get_file_size, get_file_modified_time
from utilities.database import initialize_database, get_pending_files, update_file_hash_batch, get_last_scan_timestamp, update_last_scan_timestamp, _chunk_data
from utilities.html_generator import generate_html_report

from sqlalchemy import Column, Integer, String, BigInteger, Float, Table, MetaData, select, insert


def optimized_file_hash(file_path, algorithm, chunk_size=1024*1024):
    """An optimized version of calculate_file_hash with larger buffer size"""
    try:
        from hashlib import new
        hash_obj = new(algorithm)
        
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                hash_obj.update(chunk)
                
        return hash_obj.hexdigest()
    except Exception as e:
        print(f"Error calculating hash for {file_path}: {e}")
        return None


def process_file_hash(args):
    """Process a single file hash calculation"""
    file_id, file_path, algorithm, chunk_size = args
    try:
        hash_value = optimized_file_hash(file_path, algorithm, chunk_size)
        if hash_value:
            return (file_id, hash_value)
        return None
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None


def main():
    """Main entry point for the file hash scanner."""
    parser = argparse.ArgumentParser(
        description="Scan files in a directory, calculate hashes, store in SQLite, and generate HTML reports.",
        epilog="""
Examples:
  python main_mul.py /path/to/scan -p 4  # Use 4 processes
  python main_mul.py /path/to/scan -a sha1 -c 8MB -b 2000 -v  # Custom perf + core with verbose
  python main_mul.py /path/to/scan -p 8 -c 8388608 -b 500  # Explicit 8MB chunk, small batches
Note: Optimal for large scans; auto-detects CPU cores.
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--version', action='version', version='%(prog)s 1.0 (dupFinder File Hash Scanner)')

    core_group = parser.add_argument_group('Core Options')
    core_group.add_argument("path", help="Path to the directory to scan recursively or a single file. Required.")
    core_group.add_argument(
        "-a", "--algorithm", choices=['md5', 'sha1', 'sha256', 'sha512'], default="md5",
        help="Hashing algorithm. Possible values: %(choices)s. Default: %(default)s."
    )
    core_group.add_argument(
        "-d", "--database", default="./outputs/file_hashes.db",
        help="Path to the SQLite database file for storing file metadata and hashes. Default: %(default)s."
    )
    core_group.add_argument(
        "-r", "--report", default="./outputs/hash_report.html",
        help="Path for the generated interactive HTML report. Default: %(default)s."
    )
    core_group.add_argument(
        "-v", "--verbose", action='store_true',
        help="Enable verbose output for detailed processing information and debug logging."
    )

    perf_group = parser.add_argument_group('Performance Options')
    perf_group.add_argument(
        "-p", "--processes", type=int, default=multiprocessing.cpu_count(),
        help="Number of parallel processes for hash calculation. Use 0 for auto (CPU cores). Default: %(default)s."
    )
    perf_group.add_argument(
        "-c", "--chunk-size", type=int, default=4*1024*1024,
        help="Buffer size for reading files during hashing (bytes). Larger values improve I/O for big files but increase memory use. Default: %(default)s (4MB). Examples: 1MB=1048576, 8MB=8388608."
    )
    perf_group.add_argument(
        "-b", "--batch-size", type=int, default=1000,
        help="Number of hashes to process and commit to database in batches. Higher values reduce DB overhead but increase memory. Default: %(default)s."
    )

    args = parser.parse_args()
    path = args.path

    # Check if path exists
    if not os.path.exists(path):
        print(f"Error: Path not found -> {path}")
        return 1

    try:
        total_start_time = time.time()
        
        # Initialize database with optimizations
        print(f"Initializing database at {args.database}")
        conn = initialize_database(args.database)
        # Import engine after initialization to get the updated value
        from utilities.database import engine
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.commit()

        # --- PHASE 1: DISCOVERY ---
        print(f"\n--- Phase 1: Discovery ---")
        print(f"Scanning directory structure: {path}")
        
        discovery_start = time.time()
        files_to_upsert = []
        
        if os.path.isfile(path):
            file_size = get_file_size(path)
            modified_time = get_file_modified_time(path)
            scan_date = time.time()
            files_to_upsert.append((os.path.basename(path), path, file_size, scan_date, modified_time))
        else:
            # Walk directory and collect metadata
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        if args.verbose:
                            print(f"Discovering {file_path}")
                        file_size = os.path.getsize(file_path)
                        modified_time = get_file_modified_time(file_path)
                        scan_date = time.time()
                        files_to_upsert.append((file, file_path, file_size, scan_date, modified_time))
                    except OSError as e:
                        print(f"Error accessing {file_path}: {e}")
                        if args.verbose:
                            import traceback
                            traceback.print_exc()

        print(f"Found {len(files_to_upsert)} files. Syncing with database...")
        
        # Batch query existing files
        paths = [item[1] for item in files_to_upsert]
        existing_files = {}
        last_scan_ts = get_last_scan_timestamp()
        
        metadata = MetaData()
        table = Table('file_hashes', metadata,
                     Column('id', Integer, primary_key=True),
                     Column('filename', String, nullable=False),
                     Column('absolute_path', String, nullable=False, unique=True),
                     Column('hash_value', String, nullable=True),
                     Column('file_size', BigInteger, nullable=False),
                     Column('scan_date', Float, nullable=False),
                     Column('modified_time', Float, nullable=True),
                     extend_existing=True)
        
        with engine.connect() as connection:
            for chunk_paths in _chunk_data(paths, 900):
                query = select(table.c.absolute_path, table.c.file_size, table.c.hash_value, table.c.modified_time).where(table.c.absolute_path.in_(chunk_paths))
                result = connection.execute(query)
                for row in result:
                    existing_files[row.absolute_path] = {
                        'file_size': row.file_size,
                        'hash_value': row.hash_value,
                        'modified_time': row.modified_time
                    }
        
        # Process each file
        inserts = []
        updates = []
        skipped_count = 0
        
        with tqdm(total=len(files_to_upsert), desc="Processing metadata") as pbar:
            for item in files_to_upsert:
                filename, abs_path, size, scan_date, modified_time = item
                stored = existing_files.get(abs_path)
                hash_to_set = ''
                if (stored and
                    stored['hash_value'] and stored['hash_value'] != '' and
                    stored['modified_time'] is not None and
                    last_scan_ts is not None and
                    stored['file_size'] == size and
                    stored['modified_time'] >= last_scan_ts and
                    modified_time <= stored['modified_time']):
                    hash_to_set = stored['hash_value']
                    skipped_count += 1
                
                values = {
                    'filename': filename,
                    'absolute_path': abs_path,
                    'file_size': size,
                    'scan_date': scan_date,
                    'modified_time': modified_time,
                    'hash_value': hash_to_set
                }
                
                if stored:
                    updates.append(values)
                else:
                    inserts.append(values)
                
                pbar.update(1)
        
        # Batch insert and update
        with engine.begin() as connection:
            if inserts:
                connection.execute(insert(table), inserts)
            for update_item in updates:
                stmt = table.update().where(table.c.absolute_path == update_item['absolute_path']).values(**update_item)
                connection.execute(stmt)
        
        print(f"Processed metadata. Skipped hashing {skipped_count} unchanged files.")
        print(f"Discovery completed in {time.time() - discovery_start:.2f} seconds")

        # --- PHASE 2: PROCESSING ---
        print(f"\n--- Phase 2: Processing ---")
        
        # Get files that need hashing
        pending_files = get_pending_files(conn)
        
        if not pending_files:
            print("All files are already hashed. Nothing to do.")
        else:
            print(f"Found {len(pending_files)} files pending hash calculation.")
            
            # Sort by size (Largest first) to avoid tail latency
            # We need to fetch sizes first? get_pending_files only returns ID and Path.
            # Ideally we should fetch size in get_pending_files too.
            # For now, let's just process them. The OS cache might help.
            # Optimization: We could modify get_pending_files to return size and sort in SQL.
            # But let's stick to the plan.
            
            print(f"Calculating {args.algorithm.upper()} hashes using {args.processes} processes...")
            processing_start = time.time()
            
            # Prepare arguments
            # (file_id, file_path, algorithm, chunk_size)
            process_args = [
                (pid, ppath, args.algorithm, args.chunk_size) 
                for pid, ppath in pending_files
            ]
            
            # Process in batches to update DB incrementally
            total_files = len(process_args)
            batch_size = args.batch_size
            
            with ProcessPoolExecutor(max_workers=args.processes) as executor:
                with tqdm(total=total_files, desc="Hashing files") as pbar:
                    # We process all files, but we collect results in chunks to write to DB
                    # Using executor.map is easiest, but we want to batch DB writes.
                    # Let's use a generator approach or just collect chunks.
                    
                    # Chunk the input arguments for better memory management if list is huge
                    # But we already have the list in memory.
                    
                    # Submit all tasks
                    # To avoid submitting millions of tasks at once, we can chunk the submission too.
                    # But ProcessPoolExecutor handles this reasonably well.
                    
                    # Better approach: Use imap_unordered or map and iterate
                    results_iterator = executor.map(process_file_hash, process_args, chunksize=10)
                    
                    current_batch = []
                    for result in results_iterator:
                        if result:
                            current_batch.append(result)
                        
                        pbar.update(1)
                        
                        if args.verbose and len(current_batch) % 100 == 0:
                            print(f"Processed batch of {len(current_batch)} hashes so far...")
                        
                        # If batch is full, write to DB
                        if len(current_batch) >= batch_size:
                            update_file_hash_batch(conn, current_batch)
                            current_batch = []
                    
                    # Write remaining
                    if current_batch:
                        update_file_hash_batch(conn, current_batch)
            
            print(f"Processing completed in {time.time() - processing_start:.2f} seconds")

        # Update last scan timestamp
        update_last_scan_timestamp(time.time())
        
        # Generate HTML report
        print("\nGenerating HTML report...")
        generate_html_report(args.database, args.report)

        total_time = time.time() - total_start_time
        print(f"\nTotal execution time: {total_time:.2f} seconds")
        print(f"Database: {args.database}")
        print(f"HTML Report: {args.report}")

        conn.close()
        return 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    # This is important for Windows compatibility
    multiprocessing.freeze_support()
    sys.exit(main())