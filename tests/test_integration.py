import os
import time
import tempfile
import shutil
from datetime import datetime
import pytest
from utilities.database import (
    initialize_database,
    get_pending_files,
    update_file_hash_batch,
    get_last_scan_timestamp,
    update_last_scan_timestamp,
    upsert_file_entry,
    get_file_by_path,
    engine
)
from utilities.hash_calculator import calculate_file_hash, get_file_mtime, get_file_size
from utilities.database import engine  # For direct queries if needed


@pytest.fixture(scope="function")
def temp_scan_dir():
    """Create a temporary directory with test files."""
    temp_dir = tempfile.mkdtemp()
    try:
        # Create test files
        file1_path = os.path.join(temp_dir, "file1.txt")
        file2_path = os.path.join(temp_dir, "file2.txt")
        
        with open(file1_path, "w") as f:
            f.write("content1")
        with open(file2_path, "w") as f:
            f.write("content2")
        
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    try:
        initialize_database(db_path)
        yield db_path
    finally:
        global engine
        if engine:
            engine.dispose()
        engine = None
        import time
        time.sleep(0.5)
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except PermissionError:
                pass


def scan_directory(temp_dir, db_path, algorithm="sha256", simulate_hash_time=False):
    """
    Simulate a full scan of the directory.
    
    Args:
        temp_dir: Directory to scan
        db_path: Database path
        algorithm: Hash algorithm
        simulate_hash_time: If True, add artificial delay to simulate hashing time
        
    Returns:
        Time taken for scan, number of files hashed
    """
    start_time = time.time()
    hashed_count = 0
    
    # Discovery: Walk and upsert metadata
    files = []
    for root, _, filenames in os.walk(temp_dir):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            file_size = get_file_size(file_path)
            mtime = get_file_mtime(file_path)
            scan_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            files.append((filename, file_path, file_size, scan_date, mtime))
    
    # Upsert metadata (this will handle skipping unchanged)
    for item in files:
        filename, abs_path, size, scan_date, mtime = item
        # In real scan, this would use the batch logic, but for test, upsert directly
        upsert_file_entry(abs_path, filename, size, mtime, scan_date=scan_date)
    
    # Get pending files and hash them
    pending = get_pending_files(None)  # conn is None, uses global engine
    for file_id, file_path in pending:
        if simulate_hash_time:
            time.sleep(0.01)  # Simulate hashing time
        hash_value = calculate_file_hash(file_path, algorithm)
        update_file_hash_batch(None, [(file_id, hash_value)])
        hashed_count += 1
    
    scan_time = time.time() - start_time
    update_last_scan_timestamp(time.time())
    return scan_time, hashed_count


def test_integration_mtime_optimization(temp_scan_dir, temp_db):
    """Test that only changed files are re-hashed after mtime modification."""
    # First scan
    scan_time1, hashed1 = scan_directory(temp_scan_dir, temp_db, simulate_hash_time=True)
    assert hashed1 == 2  # Both files hashed initially
    
    # Record initial hashes and mtimes
    file1_path = os.path.join(temp_scan_dir, "file1.txt")
    file2_path = os.path.join(temp_scan_dir, "file2.txt")
    
    initial_file1 = get_file_by_path(file1_path)
    initial_file2 = get_file_by_path(file2_path)
    initial_hashes = {initial_file1['hash_value'], initial_file2['hash_value']}
    
    # Modify mtime of file1 (simulate file change)
    new_mtime = get_file_mtime(file1_path) + 3600  # 1 hour newer
    os.utime(file1_path, (new_mtime - 3600, new_mtime))  # Set access and mod time
    
    # Second scan
    scan_time2, hashed2 = scan_directory(temp_scan_dir, temp_db, simulate_hash_time=True)
    
    # Verify only file1 was re-hashed
    assert hashed2 == 1  # Only one pending
    
    # Check that file1 hash is updated, file2 is unchanged
    after_file1 = get_file_by_path(file1_path)
    after_file2 = get_file_by_path(file2_path)
    
    assert after_file1['hash_value'] == initial_file1['hash_value']  # Re-hashed but content unchanged
    assert after_file2['hash_value'] == initial_file2['hash_value']  # Unchanged
    
    # Time savings: second scan should be faster (less hashing)
    assert scan_time2 < scan_time1  # Since only one file hashed vs two


def test_integration_no_changes(temp_scan_dir, temp_db):
    """Test that no files are re-hashed if nothing changed."""
    # First scan
    scan_time1, hashed1 = scan_directory(temp_scan_dir, temp_db)
    assert hashed1 == 2
    
    # Second scan without changes
    scan_time2, hashed2 = scan_directory(temp_scan_dir, temp_db)
    
    assert hashed2 == 0  # No pending files


def test_integration_new_file(temp_scan_dir, temp_db):
    """Test that new files are hashed."""
    # First scan (only file1)
    file1_path = os.path.join(temp_scan_dir, "file1.txt")
    temp_subdir = os.path.join(temp_scan_dir, "subdir")
    os.mkdir(temp_subdir)
    # Don't create file2 yet
    
    # Scan only file1
    files = [(os.path.basename(file1_path), file1_path, get_file_size(file1_path),
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"), get_file_mtime(file1_path))]
    for item in files:
        filename, abs_path, size, scan_date, mtime = item
        upsert_file_entry(abs_path, filename, size, mtime, scan_date=scan_date)
    pending = get_pending_files(None)
    for fid, fpath in pending:
        h = calculate_file_hash(fpath)
        update_file_hash_batch(None, [(fid, h)])
    update_last_scan_timestamp(time.time())
    
    # Add new file
    file2_path = os.path.join(temp_scan_dir, "file2.txt")
    with open(file2_path, "w") as f:
        f.write("new content")
    
    # Second scan
    scan_time2, hashed2 = scan_directory(temp_scan_dir, temp_db)
    
    assert hashed2 == 1  # Only new file hashed