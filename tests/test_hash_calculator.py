import os
import pytest
from unittest.mock import patch, mock_open
from utilities.hash_calculator import get_file_mtime, get_file_size, calculate_file_hash


def test_get_file_mtime_success():
    """Test successful mtime retrieval."""
    test_path = "/test/path/file.txt"
    mock_mtime = 1234567890.0
    
    with patch('os.path.getmtime', return_value=mock_mtime):
        result = get_file_mtime(test_path)
        assert result == mock_mtime


def test_get_file_mtime_error():
    """Test mtime retrieval with error."""
    test_path = "/test/path/file.txt"
    
    with patch('os.path.getmtime', side_effect=OSError("Permission denied")):
        result = get_file_mtime(test_path)
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