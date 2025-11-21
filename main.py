#!/usr/bin/env python3
"""
File Hash Scanner - Main Entry Point

This script provides a command line interface for scanning files,
calculating their hashes, storing them in SQLite, and generating HTML reports.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from tqdm import tqdm

# Custom Module Imports
from utilities.hash_calculator import calculate_file_hash, get_file_size
from utilities.database import initialize_database, upsert_files, get_pending_files, update_file_hash
from utilities.html_generator import generate_html_report


def main():
    """Main entry point for the file hash scanner."""
    parser = argparse.ArgumentParser(
        description="Calculate hashes for all files in a directory recursively and store in SQLite database."
    )
    parser.add_argument("path", help="Path to the directory or file to scan.")
    parser.add_argument(
        "-a", "--algorithm", default="sha256", help="Hash algorithm (md5, sha1, sha256, etc.)"
    )
    parser.add_argument(
        "-d", "--database", default="./outputs/file_hashes.db", help="SQLite database file path"
    )
    parser.add_argument(
        "-r", "--report", default="./outputs/hash_report.html", help="Output HTML report file path"
    )

    args = parser.parse_args()
    path = args.path

    # Check if path exists
    if not os.path.exists(path):
        print(f"Error: Path not found -> {path}")
        return 1

    try:
        # Initialize database
        print(f"Initializing database at {args.database}")
        conn = initialize_database(args.database)

        # --- PHASE 1: DISCOVERY ---
        print(f"\n--- Phase 1: Discovery ---")
        print(f"Scanning directory structure: {path}")
        
        discovery_start = time.time()
        files_to_upsert = []
        
        if os.path.isfile(path):
            file_size = get_file_size(path)
            scan_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            files_to_upsert.append((os.path.basename(path), path, file_size, scan_date))
        else:
            # Walk directory and collect metadata
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_size = os.path.getsize(file_path)
                        scan_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        files_to_upsert.append((file, file_path, file_size, scan_date))
                    except OSError as e:
                        print(f"Error accessing {file_path}: {e}")

        print(f"Found {len(files_to_upsert)} files. Syncing with database...")
        
        # Upsert to DB (Insert new, Update changed, Reset hash if changed)
        # We do this in chunks to show progress
        chunk_size = 5000
        with tqdm(total=len(files_to_upsert), desc="Syncing metadata") as pbar:
            for i in range(0, len(files_to_upsert), chunk_size):
                chunk = files_to_upsert[i:i+chunk_size]
                upsert_files(conn, chunk)
                pbar.update(len(chunk))
                
        print(f"Discovery completed in {time.time() - discovery_start:.2f} seconds")

        # --- PHASE 2: PROCESSING ---
        print(f"\n--- Phase 2: Processing ---")
        
        # Get files that need hashing (Hash is NULL)
        pending_files = get_pending_files(conn)
        
        if not pending_files:
            print("All files are already hashed. Nothing to do.")
        else:
            print(f"Found {len(pending_files)} files pending hash calculation.")
            print(f"Calculating {args.algorithm.upper()} hashes...")
            
            processing_start = time.time()
            
            with tqdm(total=len(pending_files), desc="Hashing files") as pbar:
                for file_id, file_path in pending_files:
                    try:
                        hash_value = calculate_file_hash(file_path, args.algorithm)
                        update_file_hash(conn, file_id, hash_value)
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")
                        # Optionally mark as error in DB? For now just skip.
                    pbar.update(1)
            
            print(f"Processing completed in {time.time() - processing_start:.2f} seconds")

        # Generate HTML report
        print("\nGenerating HTML report...")
        generate_html_report(args.database, args.report)

        print(f"\nDone!")
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
    sys.exit(main())