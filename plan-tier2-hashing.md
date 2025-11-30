# Two-Tier Hashing Optimization Implementation Plan

## Overview

Implement a two-tier hashing strategy to reduce hash calculation time by 10x for duplicate file detection. Instead of calculating full file hashes for all files, calculate quick tier1 hashes (first 64KB) for all files, then calculate full hashes only for files with matching tier1 hashes.

---

## Problem Statement

Current approach:
- Calculates full file hash for every file (slow for large files)
- For 10,000 mixed-size files: ~45 seconds
- Wasteful for unique files that don't need full hashing

Proposed solution:
- Calculate tier1_hash (first 64KB) for all files (fast)
- Calculate full hash_value only for tier1 matches (selective)
- Expected time: ~4.5 seconds (10x faster)

---

## Architecture Decision

### Multiprocessing Placement
- **NO multiprocessing in `hash_calculator.py`** - Keep as pure utility functions
- **Multiprocessing orchestration in `main_mul.py`** - Already implemented
- **Reason**: Avoid nested parallelism, maintain separation of concerns

### Database Schema Strategy
- Store `tier1_hash` for ALL files (always calculated)
- Store `hash_value` ONLY for files with tier1 matches (NULL for unique files)
- Result: 95% of files have `hash_value = NULL`

---

## What is Tier1_Hash?

**Tier1_Hash** = Hash of only the **first 64KB** of a file (instead of the entire file)

### Example
```
File: document.pdf (500MB)
├─ Tier1_Hash = MD5(first 64KB) = "a1b2c3d4..." ← FAST (milliseconds)
└─ Full_Hash = MD5(entire 500MB) = "x9y8z7w6..." ← SLOW (seconds)
```

### How It Increases Efficiency

**Scenario: Scanning 10,000 files with mixed sizes**

Without Tier1 (Current Approach):
```
File 1 (100MB)  → Hash entire file → 2 seconds
File 2 (50MB)   → Hash entire file → 1 second
File 3 (1MB)    → Hash entire file → 0.05 seconds
File 4 (100MB)  → Hash entire file → 2 seconds
...
Total: ~45 seconds for 10,000 files
```

With Tier1 (Two-Tier Approach):
```
Step 1: Hash FIRST 64KB of all files (FAST)
File 1 (100MB)  → Hash first 64KB → 0.01 seconds
File 2 (50MB)   → Hash first 64KB → 0.01 seconds
File 3 (1MB)    → Hash first 64KB → 0.001 seconds
File 4 (100MB)  → Hash first 64KB → 0.01 seconds
...
Subtotal: ~0.5 seconds for all 10,000 files

Step 2: Group by Tier1_Hash
├─ Tier1 "a1b2c3d4" → Files: [file1.bin, file4.bin] (DUPLICATES!)
├─ Tier1 "x9y8z7w6" → Files: [file2.bin] (UNIQUE)
└─ Tier1 "m5n6o7p8" → Files: [file3.bin] (UNIQUE)

Step 3: Full hash ONLY for files with matching Tier1
├─ file1.bin → Full hash → 2 seconds (NEEDED - matches tier1)
├─ file4.bin → Full hash → 2 seconds (NEEDED - matches tier1)
└─ file2.bin, file3.bin → SKIP full hash (no tier1 match)

Subtotal: ~4 seconds for only 2 files

Total: ~4.5 seconds (vs 45 seconds before)
```

**Speedup: 10x faster!**

### Why This Works
1. **Most files are unique** → Tier1 hash alone proves they're different
2. **Tier1 is 95% faster** → Only hashing first 64KB instead of entire file
3. **Selective full hashing** → Only hash files that might be duplicates

---

## Database Schema Strategy

### Current Schema
```sql
CREATE TABLE file_hashes (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    file_path TEXT,
    hash_value TEXT,
    file_size INTEGER,
    scan_date TEXT
);
```

### New Schema
```sql
CREATE TABLE file_hashes (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    file_path TEXT,
    tier1_hash TEXT NOT NULL,      -- Always populated (first 64KB hash)
    hash_value TEXT,               -- NULL for unique files, populated for duplicates
    file_size INTEGER,
    scan_date TEXT
);

-- Index for fast duplicate detection
CREATE INDEX idx_tier1_hash ON file_hashes(tier1_hash);
```

### When to Populate `hash_value`
- Only when `tier1_hash` matches another file's `tier1_hash`
- This means: "These files might be duplicates, so calculate full hash to confirm"

**Result**: Most rows have `hash_value = NULL` ✓

### When You NEED the Complete Hash

**Use Case 1: Confirming Duplicates**
```
Scenario: Two files have same tier1_hash
├─ file1.bin: tier1_hash = "abc123", hash_value = "xyz789"
├─ file2.bin: tier1_hash = "abc123", hash_value = "xyz789"
└─ Conclusion: CONFIRMED DUPLICATES (both hashes match)
```

**Use Case 2: User Verification**
```
User wants to see: "Are these files actually identical?"
→ Query: SELECT * WHERE tier1_hash = 'abc123'
→ If multiple rows with same tier1_hash:
   - Calculate full hash for each
   - Store in hash_value column
   - Compare hash_value to confirm
```

**Use Case 3: Future Incremental Scans**
```
Next scan of same directory:
├─ Calculate tier1_hash for all files (fast)
├─ If tier1_hash unchanged → File hasn't changed
├─ If tier1_hash changed → File was modified
└─ Only recalculate full hash if tier1_hash changed
```

---

## Implementation Phases

### Phase 1: Enhance `hash_calculator.py` with Pure Functions

Add three new functions (keep existing functions unchanged for backward compatibility):

#### 1. `calculate_file_hash_tiered(file_path, algorithm="md5", tier1_size=65536)`
- Calculate both tier1_hash (first 64KB) and full_hash for a single file
- Returns: `(tier1_hash, full_hash)`
- No multiprocessing - pure calculation logic
- Used by both `main.py` and `main_mul.py`

```python
def calculate_file_hash_tiered(file_path: str, algorithm: str = "md5",
                               tier1_size: int = 65536) -> Tuple[str, str]:
    """
    Two-tier hashing for efficient duplicate detection.

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (md5, sha256, etc.)
        tier1_size: Size of first tier in bytes (default 64KB)

    Returns:
        Tuple of (tier1_hash, full_hash)

    Example:
        tier1, full = calculate_file_hash_tiered("large_file.bin")
        # tier1 = "a1b2c3d4..." (first 64KB hash)
        # full = "x9y8z7w6..." (entire file hash)
    """
```

#### 2. `group_files_by_size(directory: str) -> Dict[int, List[str]]`
- Group files by size to identify potential duplicates
- Return only groups with 2+ files (skip unique-sized files)
- Reduces unnecessary hashing

```python
def group_files_by_size(directory: str) -> Dict[int, List[str]]:
    """
    Group files by size to identify potential duplicates.

    Args:
        directory: Path to scan

    Returns:
        Dictionary mapping file_size -> list of file paths
        Only includes groups with 2+ files (potential duplicates)

    Example:
        groups = group_files_by_size("/path/to/scan")
        # {1024: ["/path/file1.txt", "/path/file2.txt"],
        #  2048: ["/path/file3.bin", "/path/file4.bin"]}
    """
```

#### 3. `calculate_directory_hashes_optimized(directory: str, algorithm: str = "md5") -> List[Tuple]`
- Sequential version using two-tier hashing (for `main.py`)
- Groups files by size first
- Calculates tier1_hash for all files
- Returns: `(filename, file_path, tier1_hash, full_hash, file_size, scan_date)`

```python
def calculate_directory_hashes_optimized(directory: str, algorithm: str = "md5") -> List[Tuple]:
    """
    Optimized directory scanning with two-tier hashing.

    Args:
        directory: Path to scan
        algorithm: Hash algorithm (md5, sha256, etc.)

    Returns:
        List of tuples: (filename, file_path, tier1_hash, full_hash, file_size, scan_date)
        Note: full_hash is None for unique-sized files
    """
```

---

### Phase 2: Update `main_mul.py` to Use Two-Tier Hashing

Modify multiprocessing orchestration to leverage tier1 hashing:

1. **Pre-processing (before multiprocessing)**:
   - Group files by size using `group_files_by_size()`
   - Filter to only groups with 2+ files (potential duplicates)
   - Reduces files passed to worker pool

2. **Worker pool processing**:
   - Workers call `calculate_file_hash_tiered()` on each file
   - Returns both tier1_hash and full_hash
   - Store results in database

3. **Post-processing (after multiprocessing)**:
   - Group results by tier1_hash
   - For tier1 matches: full_hash already calculated
   - For unique tier1: set full_hash to NULL

---

### Phase 3: Update Database Schema

#### Migration Strategy
- Add `tier1_hash` column to existing table
- Populate with NULL initially
- Recalculate on next scan
- Maintain backward compatibility with existing `hash_value` column

#### Query Examples

**Find potential duplicates (using tier1_hash)**:
```sql
SELECT tier1_hash, COUNT(*) as count
FROM file_hashes
GROUP BY tier1_hash
HAVING count > 1;
```

**Confirm actual duplicates (using full hash)**:
```sql
SELECT hash_value, COUNT(*) as count
FROM file_hashes
WHERE hash_value IS NOT NULL
GROUP BY hash_value
HAVING count > 1;
```

**Find files that haven't changed (incremental scan)**:
```sql
SELECT * FROM file_hashes
WHERE tier1_hash = @current_tier1_hash
AND file_path = @current_path;
```

---

## Performance Comparison

### Scenario: Scanning 10,000 files (mixed sizes)
- 8,000 unique files (different sizes)
- 2,000 potential duplicates (same size)

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total time | 45 seconds | 4.5 seconds | **10x faster** |
| Tier1 hashes calculated | 0 | 10,000 | N/A |
| Full hashes calculated | 10,000 | ~2,000 | 80% reduction |
| Storage overhead | Baseline | +1 column | Minimal |
| Accuracy | 100% | 100% | Same |

### Time Breakdown (After Optimization)
- Tier1 hashing (all 10,000 files): 0.5 seconds
- Full hashing (2,000 duplicates): 4 seconds
- Database operations: 0.5 seconds
- **Total: 5 seconds**

### Storage Efficiency

For 10,000 files:
- **Without optimization**: 10,000 full hashes = ~320KB (32 bytes × 10,000)
- **With tier1 only**: 10,000 tier1 hashes = ~320KB (same size)
- **With both (selective)**: 10,000 tier1 + 500 full = ~336KB (minimal overhead)

**Benefit**: You get duplicate detection with minimal storage cost!

---

## Implementation Checklist

### Phase 1: Code Changes
- [ ] Add `calculate_file_hash_tiered()` to `hash_calculator.py`
- [ ] Add `group_files_by_size()` to `hash_calculator.py`
- [ ] Add `calculate_directory_hashes_optimized()` to `hash_calculator.py`
- [ ] Update `main.py` to use `calculate_directory_hashes_optimized()`
- [ ] Update `main_mul.py` to use `calculate_file_hash_tiered()` in worker pool

### Phase 2: Database Changes
- [ ] Add `tier1_hash` column to `file_hashes` table
- [ ] Create index on `tier1_hash` for fast lookups
- [ ] Update database insertion logic to handle both hashes

### Phase 3: Testing & Validation
- [ ] Update `tests/test_hash_calculator.py` with tier1 tests
- [ ] Verify backward compatibility with existing queries
- [ ] Benchmark performance improvement
- [ ] Test with mixed file sizes
- [ ] Validate duplicate detection accuracy

### Phase 4: Documentation
- [ ] Update README.md with optimization details
- [ ] Document tier1_hash concept
- [ ] Add usage examples
- [ ] Update API documentation

---

## Key Design Principles

✅ **DO**:
- Keep `hash_calculator.py` as pure utility functions (no multiprocessing)
- Let `main_mul.py` handle multiprocessing orchestration
- Always calculate and store `tier1_hash`
- Calculate `hash_value` ONLY for files with matching `tier1_hash`
- Leave `hash_value = NULL` for unique files
- Use `tier1_hash` for quick duplicate detection
- Use `hash_value` for confirming actual duplicates

❌ **DON'T**:
- Add multiprocessing to `hash_calculator.py`
- Create nested parallelism
- Calculate full hash for every file
- Store both hashes for unique files
- Change existing function signatures (maintain backward compatibility)

---

## Expected Outcomes

1. **Performance**: 10x faster hash calculation for duplicate detection
2. **Accuracy**: 100% accurate duplicate detection (same as before)
3. **Storage**: Minimal overhead (1 additional column with selective population)
4. **Compatibility**: Backward compatible with existing code and queries
5. **Scalability**: Handles thousands of files efficiently with multiprocessing

---

## Notes

- MD5 is optimal for duplicate detection (not cryptography)
- Tier1 size of 64KB is a good balance between speed and collision avoidance
- Two-tier approach works best with mixed file sizes
- Incremental scanning (Phase 4) can provide additional 90% speedup on subsequent scans
