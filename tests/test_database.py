import os
import time
import pytest
import tempfile
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from utilities.database import (
    initialize_database,
    get_file_by_path,
    is_file_unchanged,
    update_last_scan_timestamp,
    get_last_scan_timestamp,
    upsert_file_entry,
    engine
)


@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary in-memory database for testing."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    try:
        # Initialize the database
        initialize_database(db_path)
        yield db_path
    finally:
        global engine
        if engine:
            engine.dispose()
        engine = None
        time.sleep(0.5)
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except PermissionError:
                pass


def test_get_file_by_path_not_found(temp_db):
    """Test get_file_by_path when file does not exist."""
    result = get_file_by_path("/nonexistent/path")
    assert result is None


def test_get_file_by_path_success(temp_db):
    """Test get_file_by_path when file exists."""
    # Insert a test entry
    upsert_file_entry(
        "/test/path/file.txt",
        "file.txt",
        1024,
        1234567890.0,
        "abc123hash",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    result = get_file_by_path("/test/path/file.txt")
    assert result is not None
    assert result["filename"] == "file.txt"
    assert result["hash_value"] == "abc123hash"
    assert result["file_size"] == 1024
    assert result["mtime"] == 1234567890.0


def test_is_file_unchanged_true(temp_db):
    """Test is_file_unchanged returns True for unchanged file."""
    # Insert a test entry
    upsert_file_entry(
        "/test/path/file.txt",
        "file.txt",
        1024,
        1234567890.0,
        "abc123hash",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    # Set last scan timestamp before the file's mtime
    update_last_scan_timestamp(1234567880.0)
    
    # Current mtime same as stored
    result = is_file_unchanged("/test/path/file.txt", 1234567890.0)
    assert result is True


def test_is_file_unchanged_false_newer_mtime(temp_db):
    """Test is_file_unchanged returns False if current mtime is newer."""
    # Insert a test entry
    upsert_file_entry(
        "/test/path/file.txt",
        "file.txt",
        1024,
        1234567890.0,
        "abc123hash",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    update_last_scan_timestamp(1234567880.0)
    
    # Current mtime newer
    result = is_file_unchanged("/test/path/file.txt", 1234567900.0)
    assert result is False


def test_is_file_unchanged_false_no_entry(temp_db):
    """Test is_file_unchanged returns False if no entry."""
    result = is_file_unchanged("/nonexistent/path", 1234567890.0)
    assert result is False


def test_is_file_unchanged_false_no_last_scan(temp_db):
    """Test is_file_unchanged returns False if no last scan timestamp."""
    upsert_file_entry(
        "/test/path/file.txt",
        "file.txt",
        1024,
        1234567890.0,
        "abc123hash",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    # No last scan timestamp set
    result = is_file_unchanged("/test/path/file.txt", 1234567890.0)
    assert result is False


def test_update_last_scan_timestamp(temp_db):
    """Test updating last scan timestamp."""
    timestamp = 1234567890.0
    update_last_scan_timestamp(timestamp)
    
    result = get_last_scan_timestamp()
    assert result == timestamp


def test_get_last_scan_timestamp_none(temp_db):
    """Test getting last scan timestamp when not set."""
    result = get_last_scan_timestamp()
    assert result is None


def test_upsert_file_entry_insert(temp_db):
    """Test upsert_file_entry for new file."""
    path = "/test/path/new.txt"
    upsert_file_entry(
        path,
        "new.txt",
        2048,
        1234567891.0,
        "def456hash"
    )
    
    result = get_file_by_path(path)
    assert result["file_size"] == 2048
    assert result["mtime"] == 1234567891.0
    assert result["hash_value"] == "def456hash"


def test_upsert_file_entry_update(temp_db):
    """Test upsert_file_entry for updating existing file."""
    path = "/test/path/update.txt"
    # Initial insert
    upsert_file_entry(
        path,
        "update.txt",
        1024,
        1234567890.0,
        "oldhash"
    )
    
    # Update with changed metadata, no hash provided (simulates discovery phase)
    upsert_file_entry(
        path,
        "update.txt",
        2048,
        1234567892.0
    )
    
    result = get_file_by_path(path)
    assert result["file_size"] == 2048
    assert result["mtime"] == 1234567892.0
    assert result["hash_value"] == ""  # Reset due to metadata change