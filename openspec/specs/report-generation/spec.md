# Report Generation Specification

## Requirements

### Requirement: HTML Report Creation
The system SHALL generate a static, interactive HTML report from the database contents, including all file records grouped by hash to highlight duplicates.

#### Scenario: Full Report Generation
- **WHEN** the generate_html_report function is called with database and output paths
- **THEN** an HTML file is created with embedded CSS/JS, containing a table of all files with columns for filename, path, hash, size, and size category

#### Scenario: Duplicate Grouping
- **WHEN** records are queried from the database
- **THEN** files are grouped by hash_value, and groups with more than one file are marked as duplicates with special styling (e.g., background color)

### Requirement: Interactive Table Features
The system SHALL use DataTables library to provide pagination, searching, sorting, and length menu options in the report table.

#### Scenario: Table Initialization
- **WHEN** the HTML is loaded in a browser
- **THEN** the table is initialized with DataTables, showing 25 rows per page by default, with options for 10/25/50/100 rows, and supports column sorting and global search

### Requirement: Filtering Capabilities
The system SHALL provide client-side filters in the report, including excluding paths containing specific text and toggling to show only duplicates.

#### Scenario: Apply Duplicate Filter
- **WHEN** the "Show only duplicates" checkbox is checked and Apply button clicked
- **THEN** the table is filtered to display only rows where the hash group has multiple files, rebuilding the table with filtered data

#### Scenario: Path Exclusion Filter
- **WHEN** text is entered in the exclude filter and Apply button clicked
- **THEN** rows with paths containing the specified text (case-insensitive) are hidden from the table

### Requirement: Path Copy Functionality
The system SHALL allow users to copy file paths to the clipboard via clickable links in the path column, with toast notifications for feedback.

#### Scenario: Copy Path Action
- **WHEN** a user clicks on a path link
- **THEN** the path is copied to the clipboard, and a toast message confirms "Copied to clipboard: [path]" appears at the bottom of the page for 3 seconds

### Requirement: Summary Information
The system SHALL display summary statistics in the report, including total number of files and the scan date from the records.

#### Scenario: Summary Display
- **WHEN** the report is generated
- **THEN** the HTML includes paragraphs showing "Total Files: [count]" and "Scan Date: [date from first record]"

### Requirement: Size Formatting and Categorization
The system SHALL format file sizes in human-readable units (e.g., KB, MB) and categorize them (e.g., Small, Medium, Large) for better readability.

#### Scenario: Size Display
- **WHEN** a file record is added to the table
- **THEN** the size column shows formatted value (e.g., "1.2 MB") and size category (e.g., "Medium") based on predefined thresholds