import argparse
import time
from collections import defaultdict
from datetime import datetime

# Custom module Imports
from utilities.utils import format_file_size, get_size_category
from utilities.database import get_all_records

def generate_html_report(output_path: str) -> None:
    """
    Generate a paginated HTML report with optimized search/filter from the database.

    Args:
        output_path: Path to save the HTML report
    """
    start_time = time.time()
    records = get_all_records()
    print(f"Retrieved {len(records)} records from database in {time.time() - start_time:.2f} seconds")
    
    # Convert scan_date epoch to local human-readable for display
    scan_date_display = 'N/A'
    if records:
        scan_epoch = records[0][4]  # scan_date is now float epoch
        if scan_epoch:
            scan_date_display = datetime.fromtimestamp(scan_epoch).strftime('%Y-%m-%d %H:%M:%S')

    # Group duplicates by hash
    hash_groups = defaultdict(list)
    for record in records:
        hash_groups[record[2]].append(record)

    duplicate_groups = {k: v for k, v in hash_groups.items() if len(v) > 1}

    html_parts = ['''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Hash Report</title>
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
    <style>
        #toast { visibility: hidden; min-width: 250px; margin-left: -125px; background-color: #333; color: #fff; text-align: center; border-radius: 4px; padding: 12px; position: fixed; z-index: 1; left: 50%; bottom: 30px; font-size: 14px; }
        #toast.show { visibility: visible; animation: fadein 0.5s, fadeout 0.5s 2.5s; }
        @keyframes fadein { from { bottom: 0; opacity: 0; } to { bottom: 30px; opacity: 1; } }
        @keyframes fadeout { from { bottom: 30px; opacity: 1; } to { bottom: 0; opacity: 0; } }
        .group-duplicate td { border-top: 2px solid #888; background-color: #f0f8ff; }
        #filterControls { margin-bottom: 20px; }
    </style>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
</head>
<body>
    <h1>File Hash Report</h1>
    <div id="filterControls">
        <p><strong>Total Files:</strong> ''' + str(len(records)) + '''</p>
        <p><strong>Scan Date:</strong> ''' + scan_date_display + '''</p>
        <div>
            <label for="excludeFilter">Exclude paths containing:</label>
            <input type="text" id="excludeFilter" placeholder="Enter text to exclude">
            <button type="button" id="applyExclude">Apply</button>
        </div>
        <div>
            <label><input type="checkbox" id="toggleDuplicates"> Show only duplicates</label>
            <button type="button" id="applyDuplicates">Apply</button>
        </div>
    </div>
    <table id="hashTable" class="display">
        <thead>
            <tr>
                <th>Filename</th>
                <th>Path</th>
                <th>Hash</th>
                <th>Size</th>
                <th>Size Category</th>
            </tr>
        </thead>
        <tbody>
''']

    # Add the initial table rows in HTML rather than JavaScript
    for hash_val, group in hash_groups.items():
        group_class = "group-duplicate" if hash_val in duplicate_groups else ""
        for row in group:
            filename, path, hash_value, size_bytes, scan_date = row
            size_formatted = format_file_size(size_bytes)
            size_category = get_size_category(size_bytes)
            html_parts.append(f'''            <tr class="{group_class}" data-hash="{hash_value}" data-duplicate="{str(hash_val in duplicate_groups).lower()}">
                <td>{filename}</td>
                <td><a href="#" class="copy-path" data-path="{path}">{path}</a></td>
                <td>{hash_value}</td>
                <td>{size_formatted}</td>
                <td>{size_category}</td>
            </tr>
''')

    html_parts.append('''        </tbody>
    </table>
    <div id="toast"></div>
    <script>
        // Function to copy path to clipboard
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(function() {
                const toast = document.getElementById("toast");
                toast.textContent = "Copied to clipboard: " + text;
                toast.className = "show";
                setTimeout(() => { toast.className = toast.className.replace("show", ""); }, 3000);
            }, function(err) {
                console.error("Failed to copy text: ", err);
            });
        }

        // Store all table data
        let allTableData = [];
        let dataTable;

        // Function to initialize/reinitialize the table
        function initializeTable(data) {
            // Destroy existing table if it exists
            if (dataTable) {
                dataTable.destroy();
                $('#hashTable tbody').empty();
            }

            // Build table rows from data
            const tbody = $('#hashTable tbody');
            data.forEach(item => {
                const rowClass = item.isDuplicate ? "group-duplicate" : "";
                const row = $(`
                    <tr class="${rowClass}" data-hash="${item.hash}" data-duplicate="${item.isDuplicate}">
                        <td>${item.filename}</td>
                        <td><a href="#" class="copy-path" data-path="${item.path}">${item.path}</a></td>
                        <td>${item.hash}</td>
                        <td>${item.size}</td>
                        <td>${item.sizeCategory}</td>
                    </tr>
                `);
                tbody.append(row);
            });

            // Initialize DataTable with the current data
            dataTable = $('#hashTable').DataTable({
                "pageLength": 25,
                "lengthMenu": [10, 25, 50, 100],
                "deferRender": true,
                "ordering": true
            });
        }

        // Function to apply filters
        function applyFilters() {
            const showOnlyDuplicates = $('#toggleDuplicates').prop('checked');
            const excludeText = $('#excludeFilter').val().toLowerCase();

            let filteredData = [...allTableData];

            // Filter by duplicates if needed
            if (showOnlyDuplicates) {
                filteredData = filteredData.filter(item => item.isDuplicate);
            }

            // Filter by exclusion text if provided
            if (excludeText) {
                filteredData = filteredData.filter(item => !item.path.toLowerCase().includes(excludeText));
            }

            // Rebuild table with filtered data
            initializeTable(filteredData);
        }

        $(document).ready(function() {
            // Extract data from initial table
            $('#hashTable tbody tr').each(function() {
                const $row = $(this);
                allTableData.push({
                    filename: $row.find('td').eq(0).text(),
                    path: $row.find('td').eq(1).text(),
                    hash: $row.data('hash'),
                    size: $row.find('td').eq(3).text(),
                    sizeCategory: $row.find('td').eq(4).text(),
                    isDuplicate: $row.data('duplicate') === true
                });
            });

            // Initialize DataTable
            dataTable = $('#hashTable').DataTable({
                "pageLength": 25,
                "lengthMenu": [10, 25, 50, 100],
                "deferRender": true,
                "ordering": true
            });

            // Event handlers for filter buttons
            $('#applyExclude, #applyDuplicates').on('click', function() {
                applyFilters();
            });

            // Handler for copy path links
            $(document).on('click', '.copy-path', function(e) {
                e.preventDefault();
                copyToClipboard($(this).data('path'));
            });
        });
    </script>
</body>
</html>
''')

    html = ''.join(html_parts)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"HTML report generated in {time.time() - start_time:.2f} seconds")
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a file hash HTML report.")
    parser.add_argument("--report", required=True, help="Output HTML file path")

    args = parser.parse_args()

    generate_html_report(args.report)