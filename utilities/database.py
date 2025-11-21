"""
Database Module

Functions for SQLite database operations using SQLAlchemy with configurable database backend.
"""

import os
from typing import List, Tuple, Optional, Dict, Any
from contextlib import contextmanager
import sqlite3
from sqlalchemy import create_engine, Column, Integer, String, BigInteger, Table, MetaData, select, insert, inspect, case
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

# Database Configuration
DB_CONFIG = {
    "type": "sqlite",  # Options: "sqlite", "mysql", "postgresql"
    "connection_params": {
        "sqlite": {
            "echo": False,  # SQL query logging
            "pool_size": 10,  # Connection pool size
            "max_overflow": 20,  # Max extra connections when pool is full
            "pool_timeout": 30,  # Seconds to wait for a connection from pool
            "pool_recycle": 1800,  # Recycle connections after seconds
            "connect_args": {"check_same_thread": False}  # Allow multithreaded access
        },
        "mysql": {
            "host": "localhost",
            "user": "root",
            "password": "",
            "database": "file_hashes",
            "port": 3306
        },
        "postgresql": {
            "host": "localhost",
            "user": "postgres",
            "password": "",
            "database": "file_hashes",
            "port": 5432
        }
    }
}

Base = declarative_base()
engine = None
SessionFactory = None


def initialize_database(db_path: str) -> sqlite3.Connection:
    """
    Initialize the database connection and create tables.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        SQLite connection object (for backward compatibility)
    """
    global engine, SessionFactory
    
    # Ensure directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        
    # Create SQLAlchemy engine
    # Use 4 slashes for absolute path on Windows, 3 for relative
    if os.name == 'nt':
        db_url = f"sqlite:///{os.path.abspath(db_path)}"
    else:
        db_url = f"sqlite:///{os.path.abspath(db_path)}"
        
    engine = create_engine(db_url, **DB_CONFIG["connection_params"]["sqlite"])
    
    # Create tables
    metadata = MetaData()
    table = Table('file_hashes', metadata,
                 Column('id', Integer, primary_key=True),
                 Column('filename', String, nullable=False),
                 Column('absolute_path', String, nullable=False, unique=True),
                 Column('hash_value', String, nullable=True),
                 Column('file_size', BigInteger, nullable=False),
                 Column('scan_date', String, nullable=False))
    
    metadata.create_all(engine)
    
    SessionFactory = scoped_session(sessionmaker(bind=engine))
    
    # Return raw sqlite connection for backward compatibility if needed
    # But prefer using engine
    return sqlite3.connect(db_path)


def save_to_database(conn: sqlite3.Connection, file_data: List[Tuple]) -> None:
    """
    Save file data to database (Legacy function, use upsert_files instead).
    
    Args:
        conn: SQLite connection object
        file_data: List of tuples (filename, absolute_path, hash_value, file_size, scan_date)
    """
    global engine
    if not engine:
        raise RuntimeError("Database not initialized")

    data_dicts = [
        {
            'filename': item[0],
            'absolute_path': item[1],
            'hash_value': item[2],
            'file_size': item[3],
            'scan_date': item[4]
        }
        for item in file_data
    ]
    
    metadata = MetaData()
    table = Table('file_hashes', metadata,
                 Column('id', Integer, primary_key=True),
                 Column('filename', String),
                 Column('absolute_path', String, unique=True),
                 Column('hash_value', String),
                 Column('file_size', BigInteger),
                 Column('scan_date', String))

    with engine.begin() as connection:
        for chunk in _chunk_data(data_dicts, 1000):
            # Use INSERT OR REPLACE logic
            for item in chunk:
                try:
                    stmt = insert(table).values(**item)
                    connection.execute(stmt)
                except:
                    # Update existing
                    stmt = table.update().where(table.c.absolute_path == item['absolute_path']).values(**item)
                    connection.execute(stmt)


def get_all_records(conn: sqlite3.Connection) -> List[Tuple]:
    """
    Retrieve all records from the database.
    
    Args:
        conn: SQLite connection object (ignored, kept for backward compatibility)
        
    Returns:
        List of tuples containing all file records
    """
    global engine
    
    if not engine:
        raise RuntimeError("Database not initialized. Call initialize_database first.")
    
    # Use SQLAlchemy Core for faster direct query
    metadata = MetaData()
    table = Table('file_hashes', metadata,
                 Column('filename', String),
                 Column('absolute_path', String),
                 Column('hash_value', String),
                 Column('file_size', BigInteger),
                 Column('scan_date', String),
                 extend_existing=True)
    
    with engine.connect() as connection:
        # Updated select syntax for SQLAlchemy 1.4+
        query = select(
            table.c.filename, 
            table.c.absolute_path, 
            table.c.hash_value, 
            table.c.file_size, 
            table.c.scan_date
        )
        result = connection.execute(query)
        return [row for row in result]

def _chunk_data(data, chunk_size):
    """Split data into chunks of specified size for batch processing."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]

# Context manager for session handling (useful for scripts that need direct session access)
@contextmanager
def get_session():
    """Context manager for handling SQLAlchemy sessions."""
    if not SessionFactory:
        raise RuntimeError("Database not initialized. Call initialize_database first.")
    
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

def upsert_files(conn: sqlite3.Connection, file_data: List[Tuple]) -> None:
    """
    Insert new files or update existing ones. 
    If a file exists but size/mtime changed, reset hash to NULL.
    
    Args:
        conn: SQLite connection object (ignored)
        file_data: List of tuples (filename, absolute_path, file_size, scan_date)
    """
    global engine
    if not engine:
        raise RuntimeError("Database not initialized")

    # Get existing files to decide what to do
    metadata = MetaData()
    table = Table('file_hashes', metadata,
                 Column('id', Integer, primary_key=True),
                 Column('filename', String),
                 Column('absolute_path', String, unique=True),
                 Column('hash_value', String, nullable=True),
                 Column('file_size', BigInteger),
                 Column('scan_date', String))

    # Extract paths to query
    paths = [item[1] for item in file_data]
    
    existing_files = {}
    with engine.connect() as connection:
        # Query in chunks to avoid too many variables
        for chunk_paths in _chunk_data(paths, 900): # SQLite limit is around 999 variables
            query = select(table.c.absolute_path, table.c.file_size).where(table.c.absolute_path.in_(chunk_paths))
            result = connection.execute(query)
            for row in result:
                existing_files[row.absolute_path] = row.file_size

    inserts = []
    updates = []

    for item in file_data:
        filename, absolute_path, file_size, scan_date = item
        
        if absolute_path not in existing_files:
            # New file
            inserts.append({
                'filename': filename,
                'absolute_path': absolute_path,
                'file_size': file_size,
                'scan_date': scan_date,
                'hash_value': ''
            })
        elif existing_files[absolute_path] != file_size:
            # Changed file (size mismatch) -> Update metadata and reset hash
            updates.append({
                'filename': filename,
                'absolute_path': absolute_path,
                'file_size': file_size,
                'scan_date': scan_date,
                'hash_value': ''
            })
        # Else: Unchanged file -> Do nothing

    with engine.begin() as connection:
        if inserts:
            connection.execute(insert(table), inserts)
        if updates:
            for update_item in updates:
                stmt = table.update().where(table.c.absolute_path == update_item['absolute_path']).values(**update_item)
                connection.execute(stmt)

def get_pending_files(conn: sqlite3.Connection) -> List[Tuple]:
    """Get all files that have no hash (hash_value IS NULL)."""
    global engine
    if not engine:
        raise RuntimeError("Database not initialized")
        
    metadata = MetaData()
    table = Table('file_hashes', metadata,
                 Column('id', Integer, primary_key=True),
                 Column('absolute_path', String),
                 Column('hash_value', String))
                 
    with engine.connect() as connection:
        query = select(table.c.id, table.c.absolute_path).where((table.c.hash_value == '') | (table.c.hash_value == None))
        result = connection.execute(query)
        return [(row.id, row.absolute_path) for row in result]

def update_file_hash(conn: sqlite3.Connection, file_id: int, hash_value: str) -> None:
    """Update the hash for a specific file ID."""
    global engine
    if not engine:
        raise RuntimeError("Database not initialized")
        
    metadata = MetaData()
    table = Table('file_hashes', metadata,
                 Column('id', Integer, primary_key=True),
                 Column('hash_value', String))
                 
    with engine.begin() as connection:
        stmt = table.update().where(table.c.id == file_id).values(hash_value=hash_value)
        connection.execute(stmt)

def update_file_hash_batch(conn: sqlite3.Connection, updates: List[Tuple[int, str]]) -> None:
    """Update hashes for a batch of files (id, hash)."""
    global engine
    if not engine:
        raise RuntimeError("Database not initialized")
        
    metadata = MetaData()
    table = Table('file_hashes', metadata,
                 Column('id', Integer, primary_key=True),
                 Column('hash_value', String))
    
    # SQLAlchemy 1.4+ supports bulk updates via list of dicts with bindparam, 
    # but simple loop in transaction is often fast enough for SQLite.
    with engine.begin() as connection:
        for file_id, hash_val in updates:
            stmt = table.update().where(table.c.id == file_id).values(hash_value=hash_val)
            connection.execute(stmt)