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
from utilities.hash_calculator import calculate_file_hash, get_file_size, get_file_modified_time
from utilities.database import initialize_database, get_pending_files, update_file_hash, update_file_hash_batch, get_last_scan_timestamp, update_last_scan_timestamp, _chunk_data
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

        # --- PHASE 1: DISCOVERY ---
        print(f"\n--- Phase 1: Discovery ---")
        print(f"Scanning directory structure: {path}")
        
        discovery_start = time.time()
        scan_date = time.time()  # Set once for all files
        files_to_upsert = []

        if os.path.isfile(path):
            abs_path = path  # Already absolute
            file_size = get_file_size(abs_path)
            modified_time = get_file_modified_time(abs_path)
            files_to_upsert.append((os.path.basename(abs_path), abs_path, file_size, scan_date, modified_time))
        else:
            # Walk directory and collect metadata
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    abs_file_path = os.path.abspath(file_path)  # Ensure absolute
                    try:
                        if args.verbose:
                            print(f"Discovering {abs_file_path}")
                        file_size = os.path.getsize(abs_file_path)
                        modified_time = get_file_modified_time(abs_file_path)
                        files_to_upsert.append((file, abs_file_path, file_size, scan_date, modified_time))
                    except OSError as e:
                        print(f"Error accessing {abs_file_path}: {e}")
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
                query = select(table.c.absolute_path, table.c.file_size, table.c.hash_value, table.c.modified_time, table.c.scan_date).where(table.c.absolute_path.in_(chunk_paths))
                result = connection.execute(query)
                for row in result:
                    existing_files[row.absolute_path] = {
                        'file_size': row.file_size,
                        'hash_value': row.hash_value,
                        'modified_time': row.modified_time,
                        'scan_date': row.scan_date
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
                    stored['file_size'] == size and
                    last_scan_ts is not None and
                    (abs(modified_time - stored['modified_time']) < 1e-6 or modified_time < last_scan_ts)):
                    hash_to_set = stored['hash_value']
                    skipped_count += 1
                else:
                    hash_to_set = ''
                
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
        
        # Get files that need hashing (Hash is NULL)
        pending_files = get_pending_files()
        
        if not pending_files:
            print("All files are already hashed. Nothing to do.")
        else:
            print(f"Found {len(pending_files)} files pending hash calculation.")
            print(f"Calculating {args.algorithm.upper()} hashes...")
            
            processing_start = time.time()
            
            with tqdm(total=len(pending_files), desc="Hashing files") as pbar:
                current_batch = []
                for file_id, file_path in pending_files:
                    try:
                        if args.verbose:
                            print(f"Hashing {file_path} with {args.algorithm}")
                        hash_value = calculate_file_hash(file_path, args.algorithm)
                        current_batch.append((file_id, hash_value))
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")
                        if args.verbose:
                            import traceback
                            traceback.print_exc()
                        # Optionally mark as error in DB? For now just skip.
                    
                    pbar.update(1)
                    
                    # If batch is full, write to DB
                    if len(current_batch) >= BATCH_SIZE:
                        update_file_hash_batch(None, current_batch)
                        current_batch = []

                # Write remaining
                if current_batch:
                    update_file_hash_batch(None, current_batch)
            
            print(f"Processing completed in {time.time() - processing_start:.2f} seconds")
        
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