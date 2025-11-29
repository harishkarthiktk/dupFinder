"""
Database Module

Functions for SQLite database operations using SQLAlchemy with configurable database backend.
"""

import os
from typing import List, Tuple, Optional, Dict, Any
from contextlib import contextmanager
import sqlite3
import json
from sqlalchemy import create_engine, Column, Integer, String, BigInteger, Float, Table, MetaData, select, insert, inspect, case, text, Index
from datetime import datetime, timezone
import time
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

Base = declarative_base()


class FileHash(Base):
    __tablename__ = 'file_hashes'
    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)
    absolute_path = Column(String, nullable=False, unique=True)
    hash_value = Column(String, nullable=True)
    file_size = Column(BigInteger, nullable=False)
    scan_date = Column(Float, nullable=False)
    modified_time = Column(Float, nullable=True)
    __table_args__ = (Index('ix_file_hashes_absolute_path', 'absolute_path'),)


class ScanMetadata(Base):
    __tablename__ = 'scan_metadata'
    id = Column(Integer, primary_key=True)
    last_scan_timestamp = Column(Float, nullable=True)


def load_config() -> Dict[str, Any]:
    """Load database configuration from config.json."""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise RuntimeError("config.json not found. Please create it with database configuration.")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid config.json: {e}")


def test_connection() -> bool:
    """Test database connection."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False
engine = None
SessionFactory = None


def initialize_database(db_url: str = None) -> None:
    """
    Initialize the database connection and create tables using ORM.
    Loads config from config.json if no db_url provided.
    """
    global engine, SessionFactory

    if db_url:
        # Override with provided URL
        if 'postgresql' in db_url:
            engine = create_engine(db_url, pool_size=20, max_overflow=30)
        else:
            engine = create_engine(db_url, connect_args={'check_same_thread': False} if 'sqlite' in db_url else {})
    else:
        config = load_config()
        db_config = config['database']
        if db_config['type'] == 'postgresql':
            url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
            engine = create_engine(url, pool_size=20, max_overflow=30)
        elif db_config['type'] == 'sqlite':
            url = f"sqlite:///{db_config['path']}"
            engine = create_engine(url, connect_args={'check_same_thread': False})
        else:
            raise ValueError(f"Unsupported database type: {db_config['type']}")

    # Create tables using ORM
    Base.metadata.create_all(engine)

    # Create SessionFactory
    SessionFactory = scoped_session(sessionmaker(bind=engine))

    # Test connection
    if not test_connection():
        raise RuntimeError("Failed to connect to database")


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
                 Column('modified_time', Float))

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


def get_all_records(conn: sqlite3.Connection = None) -> List[Tuple]:
    """
    Retrieve all records from the database.

    Args:
        conn: Ignored, kept for backward compatibility

    Returns:
        List of tuples containing all file records
    """
    with get_session() as session:
        files = session.query(FileHash).all()
        return [(f.filename, f.absolute_path, f.hash_value, f.file_size, f.scan_date) for f in files]

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
    If a file exists but size changed, reset hash to NULL.

    All paths in file_data must use full root-relative absolute paths.

    Args:
        conn: Ignored
        file_data: List of tuples (filename, absolute_path, file_size, scan_date)
    """
    with get_session() as session:
        for filename, abs_path, file_size, scan_date in file_data:
            # Check if exists
            existing = session.query(FileHash).filter_by(absolute_path=abs_path).first()
            if existing:
                if existing.file_size != file_size:
                    # Changed, reset hash
                    existing.filename = filename
                    existing.file_size = file_size
                    existing.scan_date = scan_date
                    existing.hash_value = ''
                    existing.modified_time = None
            else:
                # New
                new_file = FileHash(
                    filename=filename,
                    absolute_path=abs_path,
                    file_size=file_size,
                    scan_date=scan_date,
                    hash_value='',
                    modified_time=None
                )
                session.add(new_file)

def get_pending_files(conn: sqlite3.Connection = None) -> List[Tuple]:
    """Get all files that have no hash."""
    with get_session() as session:
        files = session.query(FileHash).filter((FileHash.hash_value == '') | (FileHash.hash_value == None)).all()
        return [(f.id, f.absolute_path) for f in files]

def update_file_hash(conn: sqlite3.Connection, file_id: int, hash_value: str) -> None:
    """Update the hash for a specific file ID."""
    with get_session() as session:
        file = session.query(FileHash).filter_by(id=file_id).first()
        if file:
            file.hash_value = hash_value

def update_file_hash_batch(conn: sqlite3.Connection, updates: List[Tuple[int, str]]) -> None:
    """Update hashes for a batch of files (id, hash)."""
    with get_session() as session:
        for file_id, hash_val in updates:
            file = session.query(FileHash).filter_by(id=file_id).first()
            if file:
                file.hash_value = hash_val


def get_last_scan_timestamp() -> Optional[float]:
    """
    Get the last scan timestamp from the database.
    """
    with get_session() as session:
        meta = session.query(ScanMetadata).first()
        return meta.last_scan_timestamp if meta else None


def update_last_scan_timestamp(timestamp: float) -> None:
    """
    Update or insert the last scan timestamp in the database.
    """
    with get_session() as session:
        meta = session.query(ScanMetadata).first()
        if meta:
            meta.last_scan_timestamp = timestamp
        else:
            new_meta = ScanMetadata(id=1, last_scan_timestamp=timestamp)
            session.add(new_meta)


def get_file_by_path(absolute_path: str) -> Optional[Dict[str, Any]]:
    """
    Get file metadata by absolute path.
    """
    with get_session() as session:
        file = session.query(FileHash).filter_by(absolute_path=absolute_path).first()
        if file:
            return {
                'filename': file.filename,
                'absolute_path': file.absolute_path,
                'hash_value': file.hash_value,
                'file_size': file.file_size,
                'scan_date': file.scan_date,
                'modified_time': file.modified_time
            }
        return None


def is_file_unchanged(absolute_path: str, current_modified_time: float) -> bool:
    """
    Check if a file is unchanged since the last scan.
    
    This checks if the file exists, has a stored modified_time from the last scan,
    and the current modified_time is not newer than the stored modified_time.
    
    Args:
        absolute_path: The absolute path of the file.
        current_modified_time: Current modification time of the file (float).
        
    Returns:
        True if unchanged (can reuse hash), False otherwise.
    """
    file_info = get_file_by_path(absolute_path)
    if not file_info or file_info['modified_time'] is None:
        return False
    
    last_scan_ts = get_last_scan_timestamp()
    if last_scan_ts is None:
        return False  # No previous scan, must hash
    
    # Check if stored modified_time is from last scan and current <= stored
    return (file_info['modified_time'] >= last_scan_ts and current_modified_time <= file_info['modified_time'])


def upsert_file_entry(absolute_path: str, filename: str, file_size: int, modified_time: float,
                      hash_value: str = None, scan_date: float = None) -> None:
    """
    Upsert a file entry with metadata.
    """
    with get_session() as session:
        current_scan_date = scan_date if scan_date is not None else time.time()

        existing = session.query(FileHash).filter_by(absolute_path=absolute_path).first()
        if existing:
            if existing.file_size != file_size or existing.modified_time != modified_time:
                existing.hash_value = ''
            elif hash_value is not None:
                existing.hash_value = hash_value
            existing.filename = filename
            existing.file_size = file_size
            existing.scan_date = current_scan_date
            existing.modified_time = modified_time
        else:
            new_hash = hash_value if hash_value is not None else ''
            new_file = FileHash(
                filename=filename,
                absolute_path=absolute_path,
                file_size=file_size,
                scan_date=current_scan_date,
                modified_time=modified_time,
                hash_value=new_hash
            )
            session.add(new_file)

