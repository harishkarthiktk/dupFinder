import os
import time
from datetime import datetime
import pytest
import tempfile
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from utilities.database import (
    initialize_database,
    get_file_by_path,
    is_file_unchanged,
    update_last_scan_timestamp,
    get_last_scan_timestamp,
    upsert_file_entry,
    upsert_files,
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
    current_epoch = time.time()
    upsert_file_entry(
        "/test/path/file.txt",
        "file.txt",
        1024,
        1234567890.0,
        "abc123hash",
        current_epoch
    )
    
    result = get_file_by_path("/test/path/file.txt")
    assert result is not None
    assert result["filename"] == "file.txt"
    assert result["hash_value"] == "abc123hash"
    assert result["file_size"] == 1024
    assert result["modified_time"] == 1234567890.0
    assert isinstance(result["scan_date"], float)
    assert abs(result["scan_date"] - current_epoch) < 1


def test_is_file_unchanged_true(temp_db):
    """Test is_file_unchanged returns True for unchanged file."""
    # Insert a test entry
    current_epoch = time.time()
    upsert_file_entry(
        "/test/path/file.txt",
        "file.txt",
        1024,
        1234567890.0,
        "abc123hash",
        current_epoch
    )
    
    # Set last scan timestamp before the file's mtime
    update_last_scan_timestamp(1234567880.0)
    
    # Current mtime same as stored
    result = is_file_unchanged("/test/path/file.txt", 1234567890.0)
    assert result is True


def test_is_file_unchanged_false_newer_modified_time(temp_db):
    """Test is_file_unchanged returns False if current modified_time is newer."""
    # Insert a test entry
    current_epoch = time.time()
    upsert_file_entry(
        "/test/path/file.txt",
        "file.txt",
        1024,
        1234567890.0,
        "abc123hash",
        current_epoch
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
    current_epoch = time.time()
    upsert_file_entry(
        "/test/path/file.txt",
        "file.txt",
        1024,
        1234567890.0,
        "abc123hash",
        current_epoch
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
    assert result["modified_time"] == 1234567891.0
    assert result["hash_value"] == "def456hash"


def test_upsert_file_entry_update(temp_db):
    """Test upsert_file_entry for updating existing file."""
    path = "/test/path/update.txt"
    current_epoch1 = time.time()
    # Initial insert
    upsert_file_entry(
        path,
        "update.txt",
        1024,
        1234567890.0,
        "oldhash",
        current_epoch1
    )
    
    current_epoch2 = time.time()
    # Update with changed metadata, no hash provided (simulates discovery phase)
    upsert_file_entry(
        path,
        "update.txt",
        2048,
        1234567892.0,
        scan_date=current_epoch2
    )
    
    result = get_file_by_path(path)
    assert result["file_size"] == 2048
    assert result["modified_time"] == 1234567892.0
    assert result["hash_value"] == ""  # Reset due to metadata change
    assert isinstance(result["scan_date"], float)  # Ensure epoch float
    assert abs(result["scan_date"] - current_epoch2) < 1


def test_upsert_file_entry_epoch_storage(temp_db):
    """Test that upsert_file_entry stores scan_date as epoch float."""
    path = "/test/path/epoch.txt"
    epoch_time = 1234567890.0
    upsert_file_entry(
        path,
        "epoch.txt",
        1024,
        1234567890.0,
        None,
        epoch_time
    )
    
    result = get_file_by_path(path)
    assert isinstance(result["scan_date"], float)
    assert result["scan_date"] == epoch_time


def test_upsert_normalization_relative_paths(temp_db):
    """Test that upsert functions normalize relative paths to absolute in storage."""
    current_dir = os.getcwd()
    rel_path = "test_rel.txt"
    abs_path = os.path.abspath(rel_path)
    current_epoch = time.time()
    
    # Test upsert_file_entry with relative path
    upsert_file_entry(
        rel_path,
        "test_rel.txt",
        1024,
        current_epoch,
        None,
        current_epoch
    )
    result_entry = get_file_by_path(abs_path)
    assert result_entry is not None
    assert result_entry["absolute_path"] == abs_path  # Normalized to absolute
    assert os.path.isabs(result_entry["absolute_path"])
    
    # Test upsert_files with relative path
    file_data = [("test_batch.txt", rel_path, 2048, current_epoch)]
    upsert_files(None, file_data)
    result_batch = get_file_by_path(abs_path)
    assert result_batch is not None
    assert result_batch["absolute_path"] == abs_path  # Normalized
    assert os.path.isabs(result_batch["absolute_path"])
    
    # Clean up
    # Note: In real test, we'd delete, but since temp_db, it's fine
