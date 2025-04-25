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
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import io

# Custom Module Imports
from utilities.hash_calculator import calculate_directory_hashes, calculate_file_hash, get_file_size
from utilities.database import initialize_database, save_to_database
from utilities.html_generator import generate_html_report


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


def process_file(file_args):
    """Process a single file and return its data"""
    file_path, algorithm, chunk_size = file_args
    try:
        start_time = time.time()
        hash_value = optimized_file_hash(file_path, algorithm, chunk_size)
        if hash_value is None:
            return None
            
        file_size = get_file_size(file_path)
        filename = os.path.basename(file_path)
        scan_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        process_time = time.time() - start_time
        return (filename, file_path, hash_value, file_size, scan_date)
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None


def group_files_by_size(files, min_batch_size=50, max_batch_size=200):
    """Group files by size to balance workload across processes"""
    small_files = []
    medium_files = []
    large_files = []
    
    for file_path in files:
        size = os.path.getsize(file_path)
        if size < 1024*1024:  # Less than 1MB
            small_files.append(file_path)
        elif size < 10*1024*1024:  # Less than 10MB
            medium_files.append(file_path)
        else:  # Large files
            large_files.append(file_path)
    
    # Balance work by combining small files into batches
    balanced_tasks = []
    
    # Add small files in batches
    for i in range(0, len(small_files), min_batch_size):
        batch = small_files[i:i+min_batch_size]
        for file in batch:
            balanced_tasks.append(file)
    
    # Add medium and large files individually
    balanced_tasks.extend(medium_files)
    balanced_tasks.extend(large_files)
    
    return balanced_tasks


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
    parser.add_argument(
        "-p", "--processes", type=int, default=multiprocessing.cpu_count(),
        help="Number of processes to use (default: number of CPU cores)"
    )
    parser.add_argument(
        "-c", "--chunk-size", type=int, default=4*1024*1024,
        help="Read buffer chunk size in bytes (default: 4MB)"
    )
    parser.add_argument(
        "-b", "--batch-size", type=int, default=1000,
        help="Number of files to process before database commit (default: 1000)"
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
        db_dir = os.path.dirname(args.database)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        conn = initialize_database(args.database)
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode = WAL")
        # Disable syncs for speed (use with caution)
        conn.execute("PRAGMA synchronous = OFF")
        # Larger cache for better performance
        conn.execute("PRAGMA cache_size = 10000")
        conn.commit()

        # Process files
        print(f"Calculating {args.algorithm.upper()} hashes for all files in: {path}")
        
        if os.path.isfile(path):
            # Single file case
            file_path = path
            with tqdm(total=1, desc="Processing file") as pbar:
                hash_value = optimized_file_hash(file_path, args.algorithm, args.chunk_size)
                file_size = get_file_size(file_path)
                filename = os.path.basename(file_path)
                scan_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                pbar.update(1)

            file_data = [(filename, file_path, hash_value, file_size, scan_date)]
        else:
            # Directory case with optimized multiprocessing
            scan_start_time = time.time()
            print("Finding all files...")
            
            # Get all files first
            all_files = []
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    all_files.append(file_path)
            
            print(f"Found {len(all_files)} files in {time.time() - scan_start_time:.2f} seconds")
            
            # Prepare arguments for multiprocessing - balance workload
            balanced_files = group_files_by_size(all_files)
            file_args = [(file_path, args.algorithm, args.chunk_size) for file_path in balanced_files]
            
            # Process files in parallel with larger chunks for efficiency
            file_data = []
            processing_start = time.time()
            
            with ProcessPoolExecutor(max_workers=args.processes) as executor:
                # Process files in parallel with progress bar
                results = list(tqdm(
                    executor.map(process_file, file_args, chunksize=max(1, len(file_args) // (args.processes * 4))),
                    total=len(file_args),
                    desc=f"Processing files (using {args.processes} processes)"
                ))
                
                # Filter out None results (from errors)
                file_data = [result for result in results if result is not None]
            
            print(f"Processed {len(file_data)} files in {time.time() - processing_start:.2f} seconds")

        # Save to database in batches for better performance
        db_start_time = time.time()
        print(f"Saving {len(file_data)} file records to database...")
        
        # Process in batches
        batch_size = args.batch_size
        with tqdm(total=len(file_data), desc="Saving to database") as pbar:
            for i in range(0, len(file_data), batch_size):
                batch = file_data[i:i+batch_size]
                save_to_database(conn, batch)
                pbar.update(len(batch))
                conn.commit()  # Commit after each batch

        print(f"Database operations completed in {time.time() - db_start_time:.2f} seconds")

        # Generate HTML report
        report_start_time = time.time()
        print("Generating HTML report...")
        
        report_dir = os.path.dirname(args.report)
        if report_dir and not os.path.exists(report_dir):
            os.makedirs(report_dir)
            
        with tqdm(total=1, desc="Generating report") as pbar:
            generate_html_report(args.database, args.report)
            pbar.update(1)
        
        print(f"Report generated in {time.time() - report_start_time:.2f} seconds")

        total_time = time.time() - total_start_time
        print(f"\nProcessed {len(file_data)} files in {total_time:.2f} seconds ({len(file_data)/total_time:.2f} files/sec)")
        print(f"Database: {args.database}")
        print(f"HTML Report: {args.report}")

        conn.close()
        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    # This is important for Windows compatibility
    multiprocessing.freeze_support()
    sys.exit(main())