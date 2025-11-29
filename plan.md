# File Skipping Logic Fix - Implementation Plan

## Problem Statement

The file skipping optimization in `main.py` and `main_mul.py` is not working correctly. Files that should be skipped (because they haven't been modified since the last scan) are being re-hashed unnecessarily.

## Root Cause Analysis

### Current Behavior (Incorrect)

The skip condition in both files checks:
```python
if (stored and
    stored['hash_value'] and stored['hash_value'] != '' and
    stored['scan_date'] is not None and
    last_scan_ts is not None and
    stored['scan_date'] >= last_scan_ts and
    stored['file_size'] == size and
    abs(modified_time - stored['modified_time']) < 1e-6):
```

**Issues:**
1. **Missing Logic:** Does NOT skip files when `modified_time < last_scan_ts` (file older than last scan)
2. **Unnecessary Check:** `stored['scan_date'] >= last_scan_ts` prevents skipping files from older scans
3. **Incomplete Condition:** Only skips if modified times are exactly equal (within 1e-6 seconds)

### Why This Fails

**Scenario:**
- Last scan: `1699999000` (Nov 15, 2023 at 10:30:00 UTC)
- File's current modified_time: `1699998000` (Nov 15, 2023 at 10:16:40 UTC) - **older than last scan**
- Stored modified_time: `1699997000` (Nov 15, 2023 at 10:03:20 UTC) - **different from current**
- File size: unchanged
- File has hash: yes

**Current Result:** File is NOT skipped (WRONG)
- Reason: `abs(1699998000 - 1699997000) = 1000` which is NOT < 1e-6

**Expected Result:** File SHOULD be skipped (CORRECT)
- Reason: `1699998000 < 1699999000` proves file hasn't been modified since last scan

## Solution

### Logic Explanation

A file can be safely skipped (reuse its hash) if:
1. File exists in the database
2. File has a valid hash (not empty)
3. File size hasn't changed
4. **AND** one of these is true:
   - The file's modification time is exactly the same as stored (file untouched)
   - **OR** the file's modification time is older than the last scan (file hasn't been modified since last scan)

### New Condition

Replace the skip condition in both `main.py` and `main_mul.py` with:

```python
if (stored and
    stored['hash_value'] and stored['hash_value'] != '' and
    stored['file_size'] == size and
    last_scan_ts is not None and
    (abs(modified_time - stored['modified_time']) < 1e-6 or modified_time < last_scan_ts)):
```

### Changes Made

| Aspect | Old | New | Reason |
|--------|-----|-----|--------|
| `stored['scan_date'] is not None` | Present | Removed | Unnecessary - file existence is sufficient |
| `stored['scan_date'] >= last_scan_ts` | Present | Removed | Incorrect - prevents skipping old scans |
| Modified time check | `abs(...) < 1e-6` | `abs(...) < 1e-6 or modified_time < last_scan_ts` | Add missing condition for old files |

## Implementation Steps

### Step 1: Update `main.py`

**File:** `main.py`
**Location:** Lines 149-156 (the skip condition)

**Action:**
1. Find the `if` statement that starts with `if (stored and`
2. Replace the entire condition with the new logic
3. Keep the body of the if statement unchanged (it sets `hash_to_set = stored['hash_value']`)

**Before:**
```python
if (stored and
    stored['hash_value'] and stored['hash_value'] != '' and
    stored['scan_date'] is not None and
    last_scan_ts is not None and
    stored['scan_date'] >= last_scan_ts and
    stored['file_size'] == size and
    abs(modified_time - stored['modified_time']) < 1e-6):
    hash_to_set = stored['hash_value']
    skipped_count += 1
```

**After:**
```python
if (stored and
    stored['hash_value'] and stored['hash_value'] != '' and
    stored['file_size'] == size and
    last_scan_ts is not None and
    (abs(modified_time - stored['modified_time']) < 1e-6 or modified_time < last_scan_ts)):
    hash_to_set = stored['hash_value']
    skipped_count += 1
```

### Step 2: Update `main_mul.py`

**File:** `main_mul.py`
**Location:** Lines 192-200 (the skip condition)

**Action:**
1. Find the `if` statement that starts with `if (stored and`
2. Replace the entire condition with the new logic
3. Keep the body of the if statement unchanged (it sets `hash_to_set = stored['hash_value']` and increments `skipped_count`)

**Before:**
```python
if (stored and
    stored['hash_value'] and stored['hash_value'] != '' and
    stored['scan_date'] is not None and
    last_scan_ts is not None and
    stored['file_size'] == size and
    stored['scan_date'] >= last_scan_ts and
    abs(modified_time - stored['modified_time']) < 1e-6):
    hash_to_set = stored['hash_value']
    skipped_count += 1
```

**After:**
```python
if (stored and
    stored['hash_value'] and stored['hash_value'] != '' and
    stored['file_size'] == size and
    last_scan_ts is not None and
    (abs(modified_time - stored['modified_time']) < 1e-6 or modified_time < last_scan_ts)):
    hash_to_set = stored['hash_value']
    skipped_count += 1
```

## Critical Points to Consider

### 1. Floating Point Comparison
- The condition uses `abs(modified_time - stored['modified_time']) < 1e-6` to compare floating point timestamps
- This is correct because file modification times can have microsecond precision
- The threshold of 1e-6 seconds (1 microsecond) is appropriate for this comparison

### 2. Timestamp Semantics
- `modified_time`: The file's actual modification timestamp (from filesystem)
- `stored['modified_time']`: The modification timestamp stored in the database from a previous scan
- `last_scan_ts`: The timestamp when the last scan completed (stored in `scan_metadata` table)
- All three are stored as epoch floats (seconds since Unix epoch)

### 3. Logic Flow
- If `modified_time < last_scan_ts`, the file definitely hasn't been modified since the last scan
- This is a safe assumption because:
  - If a file was modified after the last scan, its `modified_time` would be >= `last_scan_ts`
  - If a file's `modified_time` is older than `last_scan_ts`, it couldn't have been modified after the last scan

### 4. Edge Cases Handled
- **New files:** Won't be in `stored`, so condition fails (correct - they need hashing)
- **Modified files:** `modified_time` will be >= `last_scan_ts`, so condition fails (correct - they need re-hashing)
- **Unchanged files:** Either `modified_time` equals stored or is older than `last_scan_ts`, so condition passes (correct - skip hashing)
- **Files from old scans:** Now correctly skipped if not modified since last scan

### 5. Performance Impact
- This fix will **increase** the number of files skipped
- Result: Faster scans, reduced CPU usage, reduced disk I/O
- No negative performance impact

## Testing Recommendations

After implementation, verify:

1. **Unchanged files are skipped:** Run scan twice on same directory, second scan should skip most files
2. **Modified files are re-hashed:** Modify a file, run scan, verify it's re-hashed
3. **New files are hashed:** Add new file, run scan, verify it's hashed
4. **Skipped count increases:** Compare skipped_count output before and after fix

## Files Modified

- `main.py` - Lines 149-156
- `main_mul.py` - Lines 192-200