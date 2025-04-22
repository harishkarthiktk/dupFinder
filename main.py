#!/usr/bin/env python3
"""
File Hash Scanner - Main Entry Point

This script provides a command line interface for scanning files,
calculating their hashes, storing them in SQLite, and generating HTML reports.
"""

import argparse
import os
import sys
from datetime import datetime
from tqdm import tqdm

# Custom Module Imports
from utilities.hash_calculator import calculate_directory_hashes, calculate_file_hash, get_file_size
from utilities.database import initialize_database, save_to_database
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

        # Process files
        print(f"Calculating {args.algorithm.upper()} hashes for all files in: {path}")
        
        if os.path.isfile(path):
            # Single file case
            file_path = path
            with tqdm(total=1, desc="Processing file") as pbar:
                hash_value = calculate_file_hash(file_path, args.algorithm)
                file_size = get_file_size(file_path)
                filename = os.path.basename(file_path)
                scan_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                pbar.update(1)

            file_data = [(filename, file_path, hash_value, file_size, scan_date)]
        else:
            # Directory case - Assuming the original implementation doesn't use tqdm
            file_data = []
            # Get all files first to show accurate progress
            all_files = []
            for root, _, files in os.walk(path):
                for file in files:
                    all_files.append(os.path.join(root, file))
            
            # Process each file with progress bar
            with tqdm(total=len(all_files), desc="Processing files") as pbar:
                for file_path in all_files:
                    try:
                        hash_value = calculate_file_hash(file_path, args.algorithm)
                        file_size = get_file_size(file_path)
                        filename = os.path.basename(file_path)
                        scan_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        file_data.append((filename, file_path, hash_value, file_size, scan_date))
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")
                    pbar.update(1)

        # Save to database
        print(f"Saving {len(file_data)} file records to database...")
        with tqdm(total=len(file_data), desc="Saving to database") as pbar:
            # Since save_to_database doesn't accept a progress bar, we'll handle the progress here
            save_to_database(conn, file_data)
            pbar.update(len(file_data))  # Update all at once since we can't track individual inserts

        # Generate HTML report
        print("Generating HTML report...")
        with tqdm(total=1, desc="Generating report") as pbar:
            generate_html_report(args.database, args.report)
            pbar.update(1)

        print(f"\nProcessed {len(file_data)} files")
        print(f"Database: {args.database}")
        print(f"HTML Report: {args.report}")

        conn.close()
        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())