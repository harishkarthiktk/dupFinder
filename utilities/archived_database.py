"""
Database Module

Functions for SQLite database operations.
"""

import sqlite3
from typing import List, Tuple


def initialize_database(db_path: str) -> sqlite3.Connection:
    """
    Create or connect to the SQLite database and set up the schema.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        SQLite connection object
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table if it doesn't exist
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS file_hashes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        absolute_path TEXT NOT NULL UNIQUE,
        hash_value TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        scan_date TEXT NOT NULL
    )
    """
    )

    conn.commit()
    return conn


def save_to_database(conn: sqlite3.Connection, file_data: List[Tuple]) -> None:
    """
    Save file data to the SQLite database.
    
    Args:
        conn: SQLite connection object
        file_data: List of tuples containing (filename, absolute_path, hash_value, file_size, scan_date)
    """
    cursor = conn.cursor()
    cursor.executemany(
        """
    INSERT OR REPLACE INTO file_hashes 
    (filename, absolute_path, hash_value, file_size, scan_date)
    VALUES (?, ?, ?, ?, ?)
    """,
        file_data,
    )
    conn.commit()


def get_all_records(conn: sqlite3.Connection) -> List[Tuple]:
    """
    Retrieve all records from the database.
    
    Args:
        conn: SQLite connection object
        
    Returns:
        List of tuples containing all file records
    """
    cursor = conn.cursor()
    cursor.execute("SELECT filename, absolute_path, hash_value, file_size, scan_date FROM file_hashes")
    return cursor.fetchall()