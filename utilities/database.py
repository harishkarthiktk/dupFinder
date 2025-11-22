"""
Database Module

Functions for SQLite database operations using SQLAlchemy with configurable database backend.
"""

import os
from typing import List, Tuple, Optional, Dict, Any
from contextlib import contextmanager
import sqlite3
from sqlalchemy import create_engine, Column, Integer, String, BigInteger, Float, Table, MetaData, select, insert, inspect, case, text
from datetime import datetime, timezone
import time
from sqlalchemy.orm import declarative_base
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
    Initialize the database connection and create/update tables.
    Handles schema migrations for backward compatibility.
    """
    global engine, SessionFactory
    
    # Ensure directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        
    # Create SQLAlchemy engine
    if os.name == 'nt':
        db_url = f"sqlite:///{os.path.abspath(db_path)}"
    else:
        db_url = f"sqlite:///{os.path.abspath(db_path)}"
        
    engine = create_engine(db_url, **DB_CONFIG["connection_params"]["sqlite"])
    
    metadata = MetaData()
    # Define tables with the LATEST schema
    file_hashes_table = Table('file_hashes', metadata,
                 Column('id', Integer, primary_key=True),
                 Column('filename', String, nullable=False),
                 Column('absolute_path', String, nullable=False, unique=True),
                 Column('hash_value', String, nullable=True),
                 Column('file_size', BigInteger, nullable=False),
                 Column('scan_date', Float, nullable=False), # Latest schema
                 Column('mtime', Float, nullable=True))
    
    scan_metadata_table = Table('scan_metadata', metadata,
                                Column('id', Integer, primary_key=True),
                                Column('last_scan_timestamp', Float, nullable=True))

    inspector = inspect(engine)
    
    # Check if file_hashes table exists
    if 'file_hashes' not in inspector.get_table_names():
        print(f"Creating file_hashes table in {db_path}...")
        metadata.create_all(engine) # Create tables if they don't exist
    else:
        print(f"file_hashes table already exists in {db_path}.")
        # Check for missing columns and perform ALTER TABLE if needed
        columns = [col['name'] for col in inspector.get_columns('file_hashes')]
        
        # Add mtime column if missing
        if 'mtime' not in columns:
            print("Adding mtime column to file_hashes table...")
            with engine.begin() as conn:
                conn.execute("ALTER TABLE file_hashes ADD COLUMN mtime REAL")
        
        # Check scan_date type for migration
        scan_date_info = next((col for col in inspector.get_columns('file_hashes') if col['name'] == 'scan_date'), None)
        
        # If scan_date column exists and is TEXT, trigger migration
        if scan_date_info and str(scan_date_info['type']).upper() == 'TEXT':
            print("Detected TEXT scan_date column, initiating migration...")
            migrate_scan_date_to_epoch()
        elif not scan_date_info:
            print("scan_date column not found in existing file_hashes table. Assuming it was created correctly.")
            pass
        else:
            print("scan_date column is already FLOAT or compatible type. No migration needed.")

    # Ensure all tables are present with checkfirst
    print("Ensuring all tables are created...")
    metadata.create_all(engine, checkfirst=True)

    # Create SessionFactory after all schema adjustments
    SessionFactory = scoped_session(sessionmaker(bind=engine))
    
    # Return raw sqlite connection for backward compatibility if needed
    return sqlite3.connect(db_path)


def migrate_scan_date_to_epoch():
    """
    Migrate scan_date from TEXT datetime strings to REAL epoch floats.
    Handles data conversion and schema type change.
    """
    global engine
    if not engine:
        raise RuntimeError("Database not initialized")
    
    from datetime import datetime
    import time
    
    metadata = MetaData()
    table = Table('file_hashes', metadata,
                  Column('id', Integer, primary_key=True),
                  Column('scan_date', String),  # Temporary for selection
                  extend_existing=True)
    
    with engine.connect() as conn:
        # Fetch all rows for migration
        select_stmt = select(table.c.id, table.c.scan_date)
        result = conn.execute(select_stmt)
        rows = result.fetchall()
        
        updated_count = 0
        for row in rows:
            scan_date_str = row.scan_date
            if scan_date_str is None:
                continue
            
            try:
                # First, try if already numeric (epoch string)
                epoch = float(scan_date_str)
            except ValueError:
                try:
                    # Try to parse as datetime string, assuming UTC
                    dt = datetime.strptime(scan_date_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                    epoch = dt.timestamp()
                except ValueError:
                    # Invalid date, set to current time
                    epoch = time.time()
            
            # Update the row with float epoch (will be stored as str in TEXT, but numeric)
            update_stmt = table.update().where(table.c.id == row.id).values(scan_date=epoch)
            conn.execute(update_stmt)
            updated_count += 1
        
        conn.commit()
        print(f"Data migration completed: {updated_count} rows updated.")
    
    # Now perform schema type change to REAL
    with engine.begin() as conn:
        try:
            # Add temporary REAL column
            conn.execute(text("ALTER TABLE file_hashes ADD COLUMN scan_date_new REAL"))
            
            # Copy data with CAST (handles numeric strings to REAL)
            # For any non-numeric (shouldn't be after data migration), but CAST will NULL or error, but we handled
            conn.execute(text("UPDATE file_hashes SET scan_date_new = CAST(scan_date AS REAL) WHERE scan_date_new IS NULL OR scan_date_new = 0"))
            
            # Drop old column
            conn.execute(text("ALTER TABLE file_hashes DROP COLUMN scan_date"))
            
            # Rename new to old
            conn.execute(text("ALTER TABLE file_hashes RENAME COLUMN scan_date_new TO scan_date"))
            
            print("Schema updated: scan_date column now REAL.")
        except Exception as e:
            print(f"Schema update failed: {e}. Data migration applied, but column remains TEXT. Retrieval functions will handle casting.")
def save_to_database(conn: sqlite3.Connection, file_data: List[Tuple]) -> None:
    """
    Save file data to database (Legacy function, use upsert_files instead).
    
    Args:
        conn: SQLite connection object
        file_data: List of tuples (filename, absolute_path, hash_value, file_size, scan_date) where scan_date is epoch float
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
                 Column('scan_date', Float),
                 Column('mtime', Float))

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
                 Column('scan_date', Float),
                 Column('mtime', Float),
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
        return [(row.filename, row.absolute_path, row.hash_value, row.file_size, float(row.scan_date) if row.scan_date is not None else None) for row in result]

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
        file_data: List of tuples (filename, absolute_path, file_size, scan_date) where scan_date is epoch float
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
                 Column('scan_date', Float),
                 Column('mtime', Float))

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
                'hash_value': '',
                'mtime': None
            })
        elif existing_files[absolute_path] != file_size:
            # Changed file (size mismatch) -> Update metadata and reset hash
            updates.append({
                'filename': filename,
                'absolute_path': absolute_path,
                'file_size': file_size,
                'scan_date': scan_date,
                'hash_value': '',
                'mtime': None
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
                 Column('hash_value', String),
                 extend_existing=True)
                 
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
                 Column('hash_value', String),
                 extend_existing=True)
                 
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
                 Column('hash_value', String),
                 extend_existing=True)
    
    # SQLAlchemy 1.4+ supports bulk updates via list of dicts with bindparam, 
    # but simple loop in transaction is often fast enough for SQLite.
    with engine.begin() as connection:
        for file_id, hash_val in updates:
            stmt = table.update().where(table.c.id == file_id).values(hash_value=hash_val)
            connection.execute(stmt)


def get_last_scan_timestamp() -> Optional[float]:
    """
    Get the last scan timestamp from the database.
    
    Returns:
        The last scan timestamp as float (Unix timestamp), or None if not set.
    """
    global engine
    if not engine:
        raise RuntimeError("Database not initialized")
    
    metadata = MetaData()
    scan_table = Table('scan_metadata', metadata,
                      Column('last_scan_timestamp', Float),
                      extend_existing=True)
    
    with engine.connect() as connection:
        query = select(scan_table.c.last_scan_timestamp)
        result = connection.execute(query)
        row = result.fetchone()
        return row.last_scan_timestamp if row else None


def update_last_scan_timestamp(timestamp: float) -> None:
    """
    Update or insert the last scan timestamp in the database.
    
    Args:
        timestamp: Unix timestamp (float) for the scan completion time.
    """
    global engine
    if not engine:
        raise RuntimeError("Database not initialized")
    
    metadata = MetaData()
    scan_table = Table('scan_metadata', metadata,
                      Column('id', Integer, primary_key=True),
                      Column('last_scan_timestamp', Float),
                      extend_existing=True)
    
    with engine.begin() as connection:
        # Try to update existing, else insert
        existing = connection.execute(select(scan_table.c.id)).fetchone()
        if existing:
            stmt = scan_table.update().where(scan_table.c.id == 1).values(last_scan_timestamp=timestamp)
        else:
            stmt = insert(scan_table).values(id=1, last_scan_timestamp=timestamp)
        connection.execute(stmt)


def get_file_by_path(absolute_path: str) -> Optional[Dict[str, Any]]:
    """
    Get file metadata by absolute path.
    
    Args:
        absolute_path: The absolute path of the file.
        
    Returns:
        Dictionary with file metadata, or None if not found.
    """
    global engine
    if not engine:
        raise RuntimeError("Database not initialized")
    
    metadata = MetaData()
    table = Table('file_hashes', metadata,
                 Column('filename', String),
                 Column('absolute_path', String),
                 Column('hash_value', String),
                 Column('file_size', BigInteger),
                 Column('scan_date', Float),
                 Column('mtime', Float),
                 extend_existing=True)
    
    with engine.connect() as connection:
        query = select(table.c.filename, table.c.hash_value, table.c.file_size,
                      table.c.scan_date, table.c.mtime).where(table.c.absolute_path == absolute_path)
        result = connection.execute(query)
        row = result.fetchone()
        if row:
            return {
                'filename': row.filename,
                'hash_value': row.hash_value,
                'file_size': row.file_size,
                'scan_date': float(row.scan_date) if row.scan_date is not None else None,
                'mtime': row.mtime
            }
        return None


def is_file_unchanged(absolute_path: str, current_mtime: float) -> bool:
    """
    Check if a file is unchanged since the last scan.
    
    This checks if the file exists, has a stored mtime from the last scan,
    and the current mtime is not newer than the stored mtime.
    
    Args:
        absolute_path: The absolute path of the file.
        current_mtime: Current modification time of the file (float).
        
    Returns:
        True if unchanged (can reuse hash), False otherwise.
    """
    file_info = get_file_by_path(absolute_path)
    if not file_info or file_info['mtime'] is None:
        return False
    
    last_scan_ts = get_last_scan_timestamp()
    if last_scan_ts is None:
        return False  # No previous scan, must hash
    
    # Check if stored mtime is from last scan and current <= stored
    return (file_info['mtime'] >= last_scan_ts and current_mtime <= file_info['mtime'])


def upsert_file_entry(absolute_path: str, filename: str, file_size: int, mtime: float,
                      hash_value: str = None, scan_date: float = None) -> None:
    """
    Upsert a file entry with metadata including mtime and optional hash.
    
    If the file exists, updates the fields; if new, inserts.
    If existing file has changed (size or mtime), resets hash_value to '' to mark for re-hashing.
    
    Args:
        absolute_path: Absolute path of the file.
        filename: Filename.
        file_size: File size in bytes.
        mtime: Modification time (float).
        hash_value: Hash value (optional, set to '' if no hash).
        scan_date: Scan date string (optional, uses current if None).
    """
    global engine
    if not engine:
        raise RuntimeError("Database not initialized")
    
    from datetime import datetime
    import os
    
    current_scan_date = scan_date if scan_date is not None else time.time()
    
    metadata = MetaData()
    table = Table('file_hashes', metadata,
                 Column('id', Integer, primary_key=True),
                 Column('filename', String),
                 Column('absolute_path', String, unique=True),
                 Column('hash_value', String),
                 Column('file_size', BigInteger),
                 Column('scan_date', Float),
                 Column('mtime', Float),
                 extend_existing=True)
    
    with engine.begin() as connection:
        # Check if exists and get current metadata
        existing_query = select(table.c.file_size, table.c.mtime, table.c.hash_value).where(table.c.absolute_path == absolute_path)
        existing = connection.execute(existing_query).fetchone()
        
        values = {
            'filename': filename,
            'absolute_path': absolute_path,
            'file_size': file_size,
            'scan_date': current_scan_date,
            'mtime': mtime
        }
        
        if existing:
            # Check for changes
            if (existing.file_size != file_size or existing.mtime != mtime):
                # File changed, reset hash
                values['hash_value'] = ''
            elif hash_value is not None:
                # Use provided hash_value if given
                values['hash_value'] = hash_value
            else:
                # Keep existing hash if no change and no new hash provided
                values['hash_value'] = existing.hash_value
            
            stmt = table.update().where(table.c.absolute_path == absolute_path).values(**values)
        else:
            # New file, set hash to '' if not provided
            if hash_value is None:
                values['hash_value'] = ''
            else:
                values['hash_value'] = hash_value
            stmt = insert(table).values(**values)
        
        connection.execute(stmt)

