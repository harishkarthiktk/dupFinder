#!/usr/bin/env python3
"""
Centralized argument parser for dupFinder scripts.

This module provides a unified interface for argument parsing across
main.py and main_mul.py, reducing code duplication and ensuring
consistent argument handling.
"""

import argparse
import multiprocessing


def create_parser(include_performance_options=False):
    """
    Create and configure an argument parser for dupFinder.
    
    Args:
        include_performance_options (bool): If True, includes performance tuning options
                                           (processes, chunk-size, batch-size).
                                           Used by main_mul.py. Default: False.
    
    Returns:
        argparse.ArgumentParser: Configured parser ready to parse arguments.
    
    Examples:
        # For main.py (single-threaded)
        parser = create_parser(include_performance_options=False)
        args = parser.parse_args()
        
        # For main_mul.py (multiprocessing)
        parser = create_parser(include_performance_options=True)
        args = parser.parse_args()
    """
    
    # Determine description based on mode
    if include_performance_options:
        description = "Scan files in a directory, calculate hashes, store in database, and generate HTML reports."
        epilog = """
Examples:
  python main_mul.py /path/to/scan -p 4  # Use 4 processes
  python main_mul.py /path/to/scan -a sha1 -c 8MB -b 2000 -v  # Custom perf + core with verbose
  python main_mul.py /path/to/scan -p 8 -c 8388608 -b 500  # Explicit 8MB chunk, small batches
Note: Optimal for large scans; auto-detects CPU cores.
"""
    else:
        description = "Scan files in a directory, calculate hashes, store in database, and generate HTML reports."
        epilog = """
Examples:
  python main.py /path/to/scan  # Default settings
  python main.py /path/to/scan -a md5 -d custom.db -r report.html -v  # Custom options with verbose output
Note: For large directories, consider using main_mul.py for multiprocessing.
"""
    
    parser = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Version argument
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0 (dupFinder File Hash Scanner)'
    )
    
    # Core Options Group
    core_group = parser.add_argument_group('Core Options')
    
    core_group.add_argument(
        "path",
        help="Path to the directory to scan recursively or a single file. Required."
    )
    
    core_group.add_argument(
        "-a", "--algorithm",
        choices=['md5', 'sha1', 'sha256', 'sha512'],
        default="md5",
        help="Hashing algorithm. Possible values: %(choices)s. Default: %(default)s."
    )
    
    core_group.add_argument(
        "--db-url",
        help="Database URL to override config.json. E.g., postgresql://user:pass@host:port/db or sqlite:///path/to/db.db"
    )
    
    core_group.add_argument(
        "-r", "--report",
        default="./outputs/hash_report.html",
        help="Path for the generated interactive HTML report. Default: %(default)s."
    )
    
    core_group.add_argument(
        "-v", "--verbose",
        action='store_true',
        help="Enable verbose output for detailed processing information and debug logging."
    )
    
    core_group.add_argument(
        "--skip-html",
        action='store_true',
        help="Skip HTML report generation after scanning. Useful for batch processing or when only database updates are needed."
    )
    
    # Performance Options Group (only for multiprocessing version)
    if include_performance_options:
        perf_group = parser.add_argument_group('Performance Options')
        
        perf_group.add_argument(
            "-p", "--processes",
            type=int,
            default=multiprocessing.cpu_count(),
            help="Number of parallel processes for hash calculation. Use 0 for auto (CPU cores). Default: %(default)s."
        )
        
        perf_group.add_argument(
            "-c", "--chunk-size",
            type=int,
            default=4*1024*1024,
            help="Buffer size for reading files during hashing (bytes). Larger values improve I/O for big files but increase memory use. Default: %(default)s (4MB). Examples: 1MB=1048576, 8MB=8388608."
        )
        
        perf_group.add_argument(
            "-b", "--batch-size",
            type=int,
            default=1000,
            help="Number of hashes to process and commit to database in batches. Higher values reduce DB overhead but increase memory. Default: %(default)s."
        )
    
    return parser


def parse_arguments(include_performance_options=False):
    """
    Parse command-line arguments using the centralized parser.
    
    Args:
        include_performance_options (bool): If True, includes performance tuning options.
    
    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = create_parser(include_performance_options=include_performance_options)
    return parser.parse_args()
