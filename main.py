#!/usr/bin/env python3
"""
File Hash Scanner - Main Entry Point

This script provides a command line interface for scanning files,
calculating their hashes, storing them in SQLite, and generating HTML reports.
"""

import os
import sys
import time
from tqdm import tqdm

# Custom Module Imports
from utilities.arguments import parse_arguments
from utilities.hash_calculator import calculate_directory_hashes_optimized, calculate_file_hash_tiered, get_file_size, get_file_modified_time
from utilities.database import initialize_database, upsert_files, get_last_scan_timestamp, update_last_scan_timestamp, _chunk_data
from utilities.html_generator import generate_html_report

from sqlalchemy import Column, Integer, String, BigInteger, Float, Table, MetaData, select, insert


BATCH_SIZE = 1000  # Number of files to process before database commit


def main():
    """Main entry point for the file hash scanner."""
    args = parse_arguments(include_performance_options=False)
    path = args.path

    # Normalize path to absolute
    path = os.path.abspath(path)

    # Check if path exists
    if not os.path.exists(path):
        print(f"Error: Path not found -> {path}")
        return 1

    try:
        total_start_time = time.time()
        # Initialize database
        print("Initializing database")
        initialize_database(args.db_url)
        
        # Import engine after initialization to get the updated value
        from utilities.database import engine
    
        # Optimized scanning with two-tier hashing
        print(f"\n--- Optimized Two-Tier Hashing Scan ---")
        print(f"Scanning directory structure: {path}")
        
        optimized_start = time.time()
        scan_date = time.time()
        files_to_process = []
        
        if os.path.isfile(path):
            abs_path = path
            filename = os.path.basename(abs_path)
            file_size = get_file_size(abs_path)
            modified_time = get_file_modified_time(abs_path)
            files_to_process.append((filename, abs_path, file_size, scan_date, modified_time))
        else:
            # Discovery phase
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    abs_file_path = os.path.abspath(file_path)
                    try:
                        if args.verbose:
                            print(f"Discovering {abs_file_path}")
                        file_size = os.path.getsize(abs_file_path)
                        modified_time = get_file_modified_time(abs_file_path)
                        files_to_process.append((file, abs_file_path, file_size, scan_date, modified_time))
                    except OSError as e:
                        if args.verbose:
                            print(f"Error accessing {abs_file_path}: {e}")
                        import traceback
                        traceback.print_exc()
        
        print(f"Found {len(files_to_process)} files. Syncing with database...")
        
        # Import necessary SQLAlchemy components
        from sqlalchemy import MetaData, Table, select
        metadata = MetaData()
        table = Table('file_hashes', metadata,
                      Column('id', Integer, primary_key=True),
                      Column('filename', String, nullable=False),
                      Column('absolute_path', String, nullable=False, unique=True),
                      Column('tier1_hash', String, nullable=False),
                      Column('hash_value', String, nullable=True),
                      Column('file_size', BigInteger, nullable=False),
                      Column('scan_date', Float, nullable=False),
                      Column('modified_time', Float, nullable=True),
                      extend_existing=True)
        
        # Batch query existing files
        paths = [item[1] for item in files_to_process]
        existing_files = {}
        last_scan_ts = get_last_scan_timestamp()
        
        with engine.connect() as connection:
            for chunk_paths in _chunk_data(paths, 900):
                query = select(table.c.absolute_path, table.c.file_size, table.c.hash_value,
                              table.c.tier1_hash, table.c.modified_time, table.c.scan_date).where(
                    table.c.absolute_path.in_(chunk_paths))
                result = connection.execute(query)
                for row in result:
                    existing_files[row.absolute_path] = {
                        'file_size': row.file_size,
                        'hash_value': row.hash_value,
                        'tier1_hash': row.tier1_hash,
                        'modified_time': row.modified_time,
                        'scan_date': row.scan_date
                    }
        
        # Separate unchanged and pending
        unchanged_count = 0
        pending_list = []
        
        with tqdm(total=len(files_to_process), desc="Processing metadata") as pbar:
            for item in files_to_process:
                filename, abs_path, size, scan_date, modified_time = item
                stored = existing_files.get(abs_path)
                is_unchanged = (stored and
                                stored['hash_value'] and stored['hash_value'] != '' and
                                stored['tier1_hash'] and stored['tier1_hash'] != '' and
                                stored['file_size'] == size and
                                last_scan_ts is not None and
                                (abs(modified_time - stored['modified_time']) < 1e-6 or modified_time < last_scan_ts))
                if is_unchanged:
                    # Update scan_date for unchanged files
                    with engine.begin() as connection:
                        stmt = table.update().where(table.c.absolute_path == abs_path).values(
                            filename=filename, scan_date=scan_date, modified_time=modified_time)
                        connection.execute(stmt)
                    unchanged_count += 1
                else:
                    pending_list.append((filename, abs_path, size, scan_date, modified_time))
                pbar.update(1)
        
        print(f"Processed metadata. Skipped {unchanged_count} unchanged files.")
        
        file_hashes = []
        if pending_list:
            pending_paths = [item[1] for item in pending_list]
            print(f"Computing hashes for {len(pending_list)} pending files...")
            with tqdm(total=len(pending_list), desc="Hashing files") as pbar:
                for filename, abs_path, size, scan_date, modified_time in pending_list:
                    if args.verbose:
                        print(f"Hashing {abs_path}")
                    tier1_hash, full_hash = calculate_file_hash_tiered(abs_path, args.algorithm)
                    file_hashes.append((filename, abs_path, tier1_hash, full_hash, size, scan_date, modified_time))
                    pbar.update(1)
        
        print(f"Found and processed {len(file_hashes)} pending files with two-tier hashing.")
        
        # Upsert pending data
        if file_hashes:
            upsert_files(None, file_hashes)
        
        print(f"Optimized scan completed in {time.time() - optimized_start:.2f} seconds")
        
        # Update last scan timestamp
        update_last_scan_timestamp(time.time())

        # Generate HTML report (unless skipped)
        if not args.skip_html:
            print("\nGenerating HTML report...")
            generate_html_report(args.report)
            print(f"HTML Report: {args.report}")
        else:
            print("\nHTML report generation skipped (--skip-html flag set).")

        total_time = time.time() - total_start_time
        print(f"\nTotal execution time: {total_time:.2f} seconds")
        return 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())