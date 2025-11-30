import os
import pytest
from unittest.mock import patch, mock_open
from utilities.hash_calculator import get_file_modified_time, get_file_size, calculate_file_hash, calculate_file_hash_tiered, group_files_by_size, calculate_directory_hashes_optimized


def test_get_file_modified_time_success():
    """Test successful modified_time retrieval."""
    test_path = "/test/path/file.txt"
    mock_modified_time = 1234567890.0
    
    with patch('os.path.getmtime', return_value=mock_modified_time):
        result = get_file_modified_time(test_path)
        assert result == mock_modified_time


def test_get_file_modified_time_error():
    """Test modified_time retrieval with error."""
    test_path = "/test/path/file.txt"
    
    with patch('os.path.getmtime', side_effect=OSError("Permission denied")):
        result = get_file_modified_time(test_path)
        assert result == 0.0


def test_get_file_size_success():
    """Test successful file size retrieval."""
    test_path = "/test/path/file.txt"
    mock_size = 1024
    
    with patch('os.path.getsize', return_value=mock_size):
        result = get_file_size(test_path)
        assert result == mock_size


def test_get_file_size_error():
    """Test file size retrieval with error."""
    test_path = "/test/path/file.txt"
    
    with patch('os.path.getsize', side_effect=OSError("Permission denied")):
        result = get_file_size(test_path)
        assert result == -1


def test_calculate_file_hash_success():
    """Test successful hash calculation."""
    test_path = "/test/path/file.txt"
    mock_content = b"test content"
    expected_hash = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"
    
    with patch('builtins.open', mock_open(read_data=mock_content)):
        result = calculate_file_hash(test_path, "sha256")
        assert result == expected_hash


def test_calculate_file_hash_error():
    """Test hash calculation with error."""
    test_path = "/test/path/file.txt"
    
    with patch('builtins.open', side_effect=IOError("Cannot read file")):
        result = calculate_file_hash(test_path, "sha256")
        assert result.startswith("ERROR:")


def test_calculate_file_hash_tiered_success():
    """Test successful tiered hash calculation."""
    test_path = "/test/path/file.txt"
    mock_content = b"test content" * 10  # Enough for tier1 and full
    expected_tier1 = "d41d8cd98f00b204e9800998ecf8427e"  # MD5 of first 64KB (empty in this case, but adjust)
    expected_full = "d41d8cd98f00b204e9800998ecf8427e"  # MD5 of all
    
    with patch('builtins.open', mock_open(read_data=mock_content)):
        tier1, full = calculate_file_hash_tiered(test_path, "md5")
        assert tier1 == expected_tier1
        assert full == expected_full


def test_calculate_file_hash_tiered_compute_full_false():
    """Test tiered hash with compute_full=False."""
    test_path = "/test/path/file.txt"
    mock_content = b"test content"
    
    with patch('builtins.open', mock_open(read_data=mock_content)):
        tier1, full = calculate_file_hash_tiered(test_path, "md5", compute_full=False)
        assert full is None


def test_calculate_file_hash_tiered_error():
    """Test tiered hash calculation with error."""
    test_path = "/test/path/file.txt"
    
    with patch('builtins.open', side_effect=IOError("Cannot read file")):
        tier1, full = calculate_file_hash_tiered(test_path, "md5")
        assert tier1.startswith("ERROR:")
        assert full.startswith("ERROR:")


def test_group_files_by_size():
    """Test grouping files by size."""
    test_dir = "/test/dir"
    mock_files = [
        (1024, "/test/dir/file1.txt"),
        (1024, "/test/dir/file2.txt"),
        (2048, "/test/dir/file3.bin"),
    ]
    
    with patch('pathlib.Path.rglob') as mock_rglob:
        mock_path = mock_rglob.return_value
        mock_path.is_file.return_value = True
        mock_path.__iter__.return_value = [Path(f[1]) for f in mock_files]
        
        with patch('utilities.hash_calculator.get_file_size', side_effect=[f[0] for f in mock_files]):
            groups = group_files_by_size(test_dir)
            assert len(groups) == 1
            assert len(groups[1024]) == 2
            assert 2048 not in groups


def test_calculate_directory_hashes_optimized():
    """Test optimized directory hashing."""
    test_dir = "/test/dir"
    mock_files = [
        (1024, "/test/dir/file1.txt", "tier1_a", "full_a"),
        (1024, "/test/dir/file2.txt", "tier1_a", "full_b"),  # Same tier1, different full
        (2048, "/test/dir/file3.bin", "tier1_b", None),  # Unique size
    ]
    
    with patch('pathlib.Path.rglob') as mock_rglob:
        mock_path = mock_rglob.return_value
        mock_path.is_file.return_value = True
        mock_path.__iter__.return_value = [Path(f[1]) for f in mock_files]
        
        with patch('utilities.hash_calculator.get_file_size', side_effect=[f[0] for f in mock_files]):
            with patch('utilities.hash_calculator.get_file_modified_time', side_effect=[time.time() for _ in mock_files]):
                with patch('utilities.hash_calculator.calculate_file_hash_tiered') as mock_tiered:
                    mock_tiered.side_effect = [(f[2], f[3]) for f in mock_files]
                    results = calculate_directory_hashes_optimized(test_dir, "md5")
                    assert len(results) == 3
                    # Check that full is None for unique size
                    unique_result = next(r for r in results if r[4] == 2048)
                    assert unique_result[3] is None
                    # Check that full is computed for tier1 matches
                    match_results = [r for r in results if r[4] == 1024]
                    assert all(r[3] is not None for r in match_results)