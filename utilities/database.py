"""
Database Module

Functions for SQLite database operations using SQLAlchemy with configurable database backend.
"""

import os
from typing import List, Tuple, Optional, Dict, Any
from contextlib import contextmanager
import sqlite3
from sqlalchemy import create_engine, Column, Integer, String, BigInteger, Table, MetaData, select, insert, inspect
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

# Define the file_hashes table
class FileHash(Base):
    __tablename__ = 'file_hashes'
    
    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)
    absolute_path = Column(String, nullable=False, unique=True)
    hash_value = Column(String, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    scan_date = Column(String, nullable=False)

def get_connection_string(db_path: str) -> str:
    """Get the appropriate connection string based on DB_CONFIG."""
    db_type = DB_CONFIG["type"]
    
    if db_type == "sqlite":
        return f"sqlite:///{db_path}"
    elif db_type == "mysql":
        params = DB_CONFIG["connection_params"]["mysql"]
        return f"mysql+pymysql://{params['user']}:{params['password']}@{params['host']}:{params['port']}/{params['database']}"
    elif db_type == "postgresql":
        params = DB_CONFIG["connection_params"]["postgresql"]
        return f"postgresql://{params['user']}:{params['password']}@{params['host']}:{params['port']}/{params['database']}"
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

def initialize_database(db_path: str) -> sqlite3.Connection:
    """
    Create or connect to the SQLite database and set up the schema.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        SQLite connection object (for backward compatibility)
    """
    global engine, SessionFactory
    
    # Create directory if it doesn't exist
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    # Create SQLAlchemy engine
    connection_string = get_connection_string(db_path)
    
    # Get connection parameters based on database type
    db_type = DB_CONFIG["type"]
    connect_args = DB_CONFIG["connection_params"].get(db_type, {}).get("connect_args", {})
    
    engine = create_engine(
        connection_string,
        echo=DB_CONFIG["connection_params"][db_type].get("echo", False),
        poolclass=QueuePool,
        pool_size=DB_CONFIG["connection_params"][db_type].get("pool_size", 5),
        max_overflow=DB_CONFIG["connection_params"][db_type].get("max_overflow", 10),
        pool_timeout=DB_CONFIG["connection_params"][db_type].get("pool_timeout", 30),
        pool_recycle=DB_CONFIG["connection_params"][db_type].get("pool_recycle", 1800),
        connect_args=connect_args
    )
    
    # Create tables if they don't exist
    Base.metadata.create_all(engine)
    
    # Create session factory
    SessionFactory = scoped_session(sessionmaker(bind=engine))
    
    # For backward compatibility, return a SQLite connection
    if db_type == "sqlite":
        # Apply SQLite optimizations
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -10000")  # ~10MB cache
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.commit()
        return conn
    else:
        # Create a dummy sqlite connection for API compatibility
        # This is just to maintain the interface, but won't be used for actual operations
        return sqlite3.connect(":memory:")

def save_to_database(conn: sqlite3.Connection, file_data: List[Tuple]) -> None:
    """
    Save file data to the database using SQLAlchemy's bulk operations.
    
    Args:
        conn: SQLite connection object (ignored, kept for backward compatibility)
        file_data: List of tuples containing (filename, absolute_path, hash_value, file_size, scan_date)
    """
    global engine
    
    if not engine:
        raise RuntimeError("Database not initialized. Call initialize_database first.")
    
    # Convert file_data to list of dicts for SQLAlchemy
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
    
    # Use the most efficient method based on database type
    db_type = DB_CONFIG["type"]
    
    if db_type == "sqlite":
        # Use SQLAlchemy Core for bulk insertion (faster than ORM for bulk operations)
        metadata = MetaData()
        table = Table('file_hashes', metadata,
                     Column('id', Integer, primary_key=True),
                     Column('filename', String, nullable=False),
                     Column('absolute_path', String, nullable=False, unique=True),
                     Column('hash_value', String, nullable=False),
                     Column('file_size', BigInteger, nullable=False),
                     Column('scan_date', String, nullable=False))
        
        # SQLite-specific upsert
        with engine.begin() as connection:
            for chunk in _chunk_data(data_dicts, 1000):  # Process in chunks for better memory usage
                stmt = sqlite_insert(table).values(chunk)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['absolute_path'],
                    set_={
                        'filename': stmt.excluded.filename,
                        'hash_value': stmt.excluded.hash_value,
                        'file_size': stmt.excluded.file_size,
                        'scan_date': stmt.excluded.scan_date
                    }
                )
                connection.execute(stmt)
    else:
        # Generic approach for other database types
        with engine.begin() as connection:
            for chunk in _chunk_data(data_dicts, 1000):
                metadata = MetaData()
                table = Table('file_hashes', metadata,
                             Column('id', Integer, primary_key=True),
                             Column('filename', String, nullable=False),
                             Column('absolute_path', String, nullable=False, unique=True),
                             Column('hash_value', String, nullable=False),
                             Column('file_size', BigInteger, nullable=False),
                             Column('scan_date', String, nullable=False))
                
                for item in chunk:
                    # First try to insert
                    try:
                        stmt = insert(table).values(**item)
                        connection.execute(stmt)
                    except:
                        # If insert fails (due to unique constraint), then update
                        connection.execute(
                            table.update()
                            .where(table.c.absolute_path == item['absolute_path'])
                            .values(**item)
                        )

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