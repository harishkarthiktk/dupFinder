"""
Utilities Module

Common utility functions for the file hash scanner.
"""


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in a human-readable format.
    
    Args:
        size_bytes: File size in bytes
        
    Returns:
        Formatted file size string (e.g., "1.23 MB")
    """
    if size_bytes < 0:
        return "Unknown"

    # Define size units
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    unit_index = 0

    # Find the appropriate unit
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    # Format with appropriate precision
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.2f} {units[unit_index]}"


def get_size_category(size_bytes: int) -> str:
    """
    Get size category for filtering.
    
    Args:
        size_bytes: File size in bytes
        
    Returns:
        Size category string
    """
    if size_bytes < 0:
        return "Unknown"
    elif size_bytes < 1024 * 1024:  # Less than 1MB
        return "< 1MB"
    elif size_bytes < 5 * 1024 * 1024:  # 1-5MB
        return "1-5MB"
    elif size_bytes < 50 * 1024 * 1024:  # 5-50MB
        return "5-50MB"
    elif size_bytes < 500 * 1024 * 1024:  # 50-500MB
        return "50-500MB"
    elif size_bytes < 1024 * 1024 * 1024:  # 500MB-1GB
        return "500MB-1GB"
    elif size_bytes < 2 * 1024 * 1024 * 1024:  # 1-2GB
        return "1-2GB"
    else:  # >2GB
        return "> 2GB"