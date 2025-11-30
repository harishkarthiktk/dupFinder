"""
Hash Calculator Module

Functions for calculating file hashes and scanning directories.
This is purely referenced.
"""

import hashlib
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional, Dict


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


def get_file_modified_time(file_path: str) -> float:
    """
    Get the modification time of a file as Unix timestamp.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Modification time as float (Unix timestamp), or 0.0 if error
    """
    try:
        return os.path.getmtime(file_path)
    except (IOError, OSError) as e:
        print(f"Warning: Could not get modified_time for {file_path}: {e}", file=sys.stderr)
        return 0.0


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

from collections import defaultdict
from typing import Dict


def calculate_file_hash_tiered(file_path: str, algorithm: str = "md5",
                               tier1_size: int = 65536, compute_full: bool = True) -> Tuple[str, Optional[str]]:
    """
    Two-tier hashing for efficient duplicate detection.

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (md5, sha256, etc.)
        tier1_size: Size of first tier in bytes (default 64KB)
        compute_full: If True, compute full file hash after tier1; if False, only tier1 and return None for full

    Returns:
        Tuple of (tier1_hash, full_hash) where full_hash is None if compute_full=False

    Example:
        tier1, full = calculate_file_hash_tiered("large_file.bin")
        # tier1 = "a1b2c3d4..." (first 64KB hash)
        # full = "x9y8z7w6..." (entire file hash)
    """
    try:
        hash_func_tier1 = getattr(hashlib, algorithm)()
        hash_func_full = None
        if compute_full:
            hash_func_full = getattr(hashlib, algorithm)()
        
        with open(file_path, "rb") as f:
            first_chunk = f.read(tier1_size)
            if first_chunk:
                hash_func_tier1.update(first_chunk)
                if compute_full:
                    hash_func_full.update(first_chunk)
            
            if not compute_full:
                return hash_func_tier1.hexdigest(), None
            
            # Continue reading the rest for full hash
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                hash_func_full.update(chunk)
        
        tier1_hash = hash_func_tier1.hexdigest()
        full_hash = hash_func_full.hexdigest() if compute_full else None
        
        return tier1_hash, full_hash
    except (IOError, PermissionError) as e:
        error_str = f"ERROR: {str(e)}"
        return error_str, None if not compute_full else error_str
    except AttributeError:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def group_files_by_size(directory: str) -> Dict[int, List[str]]:
    """
    Group files by size to identify potential duplicates.

    Args:
        directory: Path to scan

    Returns:
        Dictionary mapping file_size -> list of file paths
        Only includes groups with 2+ files (potential duplicates)

    Example:
        groups = group_files_by_size("/path/to/scan")
        # {1024: ["/path/file1.txt", "/path/file2.txt"],
        #  2048: ["/path/file3.bin", "/path/file4.bin"]}
    """
    size_to_files: Dict[int, List[str]] = defaultdict(list)
    
    try:
        for path in Path(directory).rglob("*"):
            if path.is_file():
                file_size = get_file_size(str(path))
                if file_size > 0:
                    size_to_files[file_size].append(str(path))
    except Exception as e:
        print(f"Error scanning directory {directory}: {e}", file=sys.stderr)
    
    # Filter to only groups with 2+ files
    return {size: files for size, files in size_to_files.items() if len(files) >= 2}


def calculate_directory_hashes_optimized(directory: str, algorithm: str = "md5") -> List[Tuple[str, str, str, Optional[str], int, float, float]]:
    """
    Optimized directory scanning with two-tier hashing.

    Args:
        directory: Path to scan
        algorithm: Hash algorithm (md5, sha256, etc.)

    Returns:
        List of tuples: (filename, file_path, tier1_hash, full_hash, file_size, scan_date)
        Note: full_hash is None for unique-sized files or unique tier1 groups
    """
    result = []
    scan_date = time.time()
    
    try:
        # First, group all files by size
        all_size_groups = defaultdict(list)
        for path in Path(directory).rglob("*"):
            if path.is_file():
                file_size = get_file_size(str(path))
                if file_size > 0:
                    all_size_groups[file_size].append(str(path))
        
        # For unique size files (len==1), compute tier1 only
        unique_size_files = []
        potential_duplicate_groups = {}
        
        for size, files in all_size_groups.items():
            if len(files) == 1:
                unique_size_files.extend(files)
            else:
                potential_duplicate_groups[size] = files
        
        # Process unique size files: tier1 only, full=None
        for file_path in unique_size_files:
            filename = os.path.basename(file_path)
            mtime = get_file_modified_time(file_path)
            tier1_hash, _ = calculate_file_hash_tiered(file_path, algorithm, compute_full=False)
            result.append((filename, file_path, tier1_hash, None, get_file_size(file_path), scan_date, mtime))
        
        # For potential duplicates: compute tier1, group by tier1, full only for matches
        for size, files in potential_duplicate_groups.items():
            tier1_to_files = defaultdict(list)
            for file_path in files:
                filename = os.path.basename(file_path)
                mtime = get_file_modified_time(file_path)
                tier1_hash, _ = calculate_file_hash_tiered(file_path, algorithm, compute_full=False)
                tier1_to_files[tier1_hash].append((filename, file_path, mtime))
            
            # For each tier1 group
            for tier1_hash, tier1_files in tier1_to_files.items():
                if len(tier1_files) == 1:
                    # Unique tier1, full=None
                    filename, file_path, mtime = tier1_files[0]
                    result.append((filename, file_path, tier1_hash, None, size, scan_date, mtime))
                else:
                    # Matches, compute full for all in group
                    for filename, file_path, mtime in tier1_files:
                        _, full_hash = calculate_file_hash_tiered(file_path, algorithm, compute_full=True)
                        result.append((filename, file_path, tier1_hash, full_hash, size, scan_date, mtime))
        
        # Print progress every 100 files
        if len(result) % 100 == 0:
            print(f"Processed {len(result)} files...", file=sys.stderr)
            
    except Exception as e:
        print(f"Error accessing directory {directory}: {e}", file=sys.stderr)
    
    return result
if __name__ == "__main__":
    try:
        hashes = calculate_directory_hashes(sys.argv[1])
        with open (r'../outputs/directory_hashes.txt', 'w') as wfile:
            for hash in hashes:
                wfile.write("filename, file_path, hash_value, file_size" + "\n")
                wfile.writelines(f'"{hash[0]}, "{hash[1]}", "{hash[2]}", "{hash[3]}"')
    except Exception as e:
        print(f'Exception encountered: {str(e)}')