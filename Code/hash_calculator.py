"""
Hash Calculator Module

Functions for calculating file hashes and scanning directories.
"""

import hashlib
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Tuple


def calculate_file_hash(file_path: str, algorithm: str = "sha256", chunk_size: int = 8192) -> str:
    """
    Calculate hash for a single file using specified algorithm.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use (md5, sha1, sha256, etc.)
        chunk_size: Size of chunks to read at a time
        
    Returns:
        File hash as a hexadecimal string
    """
    try:
        hash_func = getattr(hashlib, algorithm)()
    except AttributeError:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    except (IOError, PermissionError) as e:
        print(f"Warning: Could not read file {file_path}: {e}", file=sys.stderr)
        return f"ERROR: {str(e)}"


def get_file_size(file_path: str) -> int:
    """
    Get the size of a file in bytes.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File size in bytes, or -1 if there was an error
    """
    try:
        return os.path.getsize(file_path)
    except (IOError, OSError) as e:
        print(f"Warning: Could not get size of file {file_path}: {e}", file=sys.stderr)
        return -1


def calculate_directory_hashes(directory: str, algorithm: str = "sha256") -> List[Tuple]:
    """
    Recursively crawl directory and calculate hashes and sizes for all files.
    
    Args:
        directory: Path to the directory to scan
        algorithm: Hash algorithm to use
        
    Returns:
        List of tuples containing (filename, absolute_path, hash_value, file_size, scan_date)
    """
    result = []
    scan_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        for path in Path(directory).rglob("*"):
            if path.is_file():
                file_path = str(path)
                hash_value = calculate_file_hash(file_path, algorithm)
                file_size = get_file_size(file_path)
                filename = os.path.basename(file_path)

                result.append((filename, file_path, hash_value, file_size, scan_date))
                # Print progress every 100 files
                if len(result) % 100 == 0:
                    print(f"Processed {len(result)} files...", file=sys.stderr)

    except Exception as e:
        print(f"Error accessing directory {directory}: {e}", file=sys.stderr)

    return result