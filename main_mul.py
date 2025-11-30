#!/usr/bin/env python3
"""
File Hash Scanner - Main Entry Point (Multiprocessing)

This script provides a command line interface for scanning files,
calculating their hashes in parallel, storing them in SQLite, and generating HTML reports.
"""

import os
import sys
import time
from tqdm import tqdm
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from typing import List, Dict, Tuple
from collections import defaultdict

# Custom Module Imports
from utilities.arguments import parse_arguments
from utilities.hash_calculator import calculate_file_hash_tiered, group_files_by_size, get_file_size, get_file_modified_time
from utilities.database import initialize_database, upsert_files, get_last_scan_timestamp, update_last_scan_timestamp, _chunk_data, FileHash, get_session
from utilities.html_generator import generate_html_report

from sqlalchemy import Column, Integer, String, BigInteger, Float, Table, MetaData, select, insert
from concurrent.futures import as_completed


def compute_tier1_worker(args):
    """Compute tier1 hash for a file"""
    path, algorithm = args
    try:
        tier1, _ = calculate_file_hash_tiered(path, algorithm, compute_full=False)
        return path, tier1
    except Exception as e:
        print(f"Error computing tier1 for {path}: {e}")
        return path, None


def compute_full_worker(args):
    """Compute full hash for a file"""
    path, algorithm = args
    try:
        _, full = calculate_file_hash_tiered(path, algorithm)
        return path, full
    except Exception as e:
        print(f"Error computing full for {path}: {e}")
        return path, None


def group_pending_by_size(pending_paths: List[str]) -> Dict[int, List[str]]:
    """Group pending paths by file size, only return groups with 2+ files."""
    size_to_paths = defaultdict(list)
    for path in pending_paths:
        size = get_file_size(path)
        if size > 0:
            size_to_paths[size].append(path)
    return {size: paths for size, paths in size_to_paths.items() if len(paths) >= 2}


def main():
    """Main entry point for the file hash scanner."""
    args = parse_arguments(include_performance_options=True)
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
                     Column('tier1_hash', String, nullable=False),
                     Column('hash_value', String, nullable=True),
                     Column('file_size', BigInteger, nullable=False),
                     Column('scan_date', Float, nullable=False),
                     Column('modified_time', Float, nullable=True),
                     extend_existing=True)
        
        with engine.connect() as connection:
            for chunk_paths in _chunk_data(paths, 900):
                query = select(table.c.absolute_path, table.c.file_size, table.c.hash_value, table.c.tier1_hash, table.c.modified_time, table.c.scan_date).where(table.c.absolute_path.in_(chunk_paths))
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
        unchanged_updates = []
        pending_list = []
        unchanged_count = 0
        
        with tqdm(total=len(files_to_upsert), desc="Processing metadata") as pbar:
            for item in files_to_upsert:
                filename, abs_path, size, scan_date, modified_time = item
                stored = existing_files.get(abs_path)
                is_unchanged = (stored and
                    stored['hash_value'] and stored['hash_value'] != '' and
                    stored['tier1_hash'] and stored['tier1_hash'] != '' and
                    stored['file_size'] == size and
                    last_scan_ts is not None and
                    (abs(modified_time - stored['modified_time']) < 1e-6 or modified_time < last_scan_ts))
                if is_unchanged:
                    values = {
                        'filename': filename,
                        'absolute_path': abs_path,
                        'tier1_hash': stored['tier1_hash'],
                        'hash_value': stored['hash_value'],
                        'file_size': size,
                        'scan_date': scan_date,
                        'modified_time': modified_time
                    }
                    unchanged_updates.append(values)
                    unchanged_count += 1
                else:
                    pending_list.append((filename, abs_path, size, scan_date, modified_time))
                pbar.update(1)
        
        # Batch update unchanged files
        if unchanged_updates:
            with engine.begin() as connection:
                for update_item in unchanged_updates:
                    stmt = table.update().where(table.c.absolute_path == update_item['absolute_path']).values(**update_item)
                    connection.execute(stmt)
        
        print(f"Processed metadata. Skipped {unchanged_count} unchanged files.")
        print(f"Discovery completed in {time.time() - discovery_start:.2f} seconds")

        # --- PHASE 2: TWO-TIER PROCESSING FOR PENDING ---
        print(f"\n--- Phase 2: Two-Tier Processing ---")
        
        if not pending_list:
            print("No pending files to process.")
        else:
            print(f"Processing {len(pending_list)} pending files with two-tier optimization.")
            processing_start = time.time()
            
            pending_paths = [item[1] for item in pending_list]
            
            # Pre-process: Group pending by size to identify potential duplicates
            size_groups = group_pending_by_size(pending_paths)
            
            # Compute tier1 for all pending in parallel
            tier1_args = [(path, args.algorithm) for path in pending_paths]
            print("Computing tier1 hashes in parallel...")
            with ProcessPoolExecutor(max_workers=args.processes) as executor:
                tier1_futures = [executor.submit(compute_tier1_worker, arg) for arg in tier1_args]
                with tqdm(total=len(tier1_args), desc="Computing tier1 hashes") as pbar:
                    tier1_results = []
                    for future in as_completed(tier1_futures):
                        tier1_results.append(future.result())
                        pbar.update(1)
            
            path_tier1 = {path: tier1 for path, tier1 in tier1_results if tier1}
            
            # Group by size and tier1 for candidates
            size_tier1_to_paths = defaultdict(list)
            path_size = {item[1]: item[2] for item in pending_list}
            for path in pending_paths:
                size = path_size[path]
                tier1 = path_tier1.get(path, '')
                if tier1:
                    size_tier1_to_paths[(size, tier1)].append(path)
            
            candidate_paths = []
            for key, paths in size_tier1_to_paths.items():
                if len(paths) > 1:
                    candidate_paths.extend(paths)
                else:
                    # Check if tier1 matches existing
                    path = paths[0]
                    tier1 = path_tier1[path]
                    with get_session() as session:
                        count = session.query(FileHash).filter(
                            FileHash.file_size == key[0],
                            FileHash.tier1_hash == tier1,
                            FileHash.hash_value.isnot(None)
                        ).count()
                    if count > 0:
                        candidate_paths.append(path)
            
            # Compute full for candidates
            path_full = {}
            if candidate_paths:
                unique_candidates = list(set(candidate_paths))
                full_args = [(path, args.algorithm) for path in unique_candidates]
                print(f"Computing full hashes for {len(unique_candidates)} candidates...")
                with ProcessPoolExecutor(max_workers=args.processes) as executor:
                    full_futures = [executor.submit(compute_full_worker, arg) for arg in full_args]
                    with tqdm(total=len(full_args), desc="Computing full hashes") as pbar:
                        full_results = []
                        for future in as_completed(full_futures):
                            full_results.append(future.result())
                            pbar.update(1)
                path_full = {path: full for path, full in full_results if full}
            
            # Prepare data for upsert
            file_hashes = []
            for item in pending_list:
                filename, abs_path, size, scan_date, modified_time = item
                tier1 = path_tier1.get(abs_path, '')
                full = path_full.get(abs_path, None)
                file_hashes.append((filename, abs_path, tier1, full, size, scan_date, modified_time))
            
            # Upsert all
            upsert_files(None, file_hashes)
            
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
    # This is important for Windows compatibility
    multiprocessing.freeze_support()
    sys.exit(main())