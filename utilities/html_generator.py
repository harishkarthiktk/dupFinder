import argparse
import time
import json
from collections import defaultdict
from datetime import datetime
from jinja2 import Template

# Custom module Imports
from utilities.utils import format_file_size, get_size_category
from utilities.database import get_all_records
import os

# HTML Template
HTML_TEMPLATE = '''<!DOCTYPE html>
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
        <p><strong>Total Files:</strong> {{ total_files }}</p>
        <p><strong>Scan Date:</strong> {{ scan_date }}</p>
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
        </tbody>
    </table>
    <div id="toast"></div>
    <script>
        const allTableData = {{ table_data_json }};
        let dataTable;

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

        function renderTable(data) {
            if (dataTable) {
                dataTable.destroy();
            }

            const tbody = document.querySelector('#hashTable tbody');
            tbody.innerHTML = '';
            
            const fragment = document.createDocumentFragment();
            for (let i = 0; i < data.length; i++) {
                const item = data[i];
                const row = document.createElement('tr');
                if (item.isDuplicate) row.className = "group-duplicate";
                row.dataset.hash = item.hash;
                row.dataset.duplicate = item.isDuplicate;
                row.innerHTML = `<td>${escapeHtml(item.filename)}</td><td><a href="#" class="copy-path" data-path="${escapeHtml(item.path)}">${escapeHtml(item.path)}</a></td><td>${escapeHtml(item.hash)}</td><td>${escapeHtml(item.size)}</td><td>${escapeHtml(item.sizeCategory)}</td>`;
                fragment.appendChild(row);
            }
            
            tbody.appendChild(fragment);

            dataTable = $('#hashTable').DataTable({
                "pageLength": 25,
                "lengthMenu": [10, 25, 50, 100],
                "deferRender": true,
                "ordering": true,
                "retrieve": true
            });
        }

        function escapeHtml(text) {
            const map = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'};
            return text.replace(/[&<>"']/g, m => map[m]);
        }

        function applyFilters() {
            const showOnlyDuplicates = document.getElementById('toggleDuplicates').checked;
            const excludeText = document.getElementById('excludeFilter').value.toLowerCase();

            let filteredData = allTableData;

            if (showOnlyDuplicates) {
                filteredData = filteredData.filter(item => item.isDuplicate);
            }

            if (excludeText) {
                filteredData = filteredData.filter(item => !item.path.toLowerCase().includes(excludeText));
            }

            renderTable(filteredData);
        }

        document.addEventListener('DOMContentLoaded', function() {
            renderTable(allTableData);
            document.getElementById('applyExclude').addEventListener('click', applyFilters);
            document.getElementById('applyDuplicates').addEventListener('click', applyFilters);
            document.addEventListener('click', function(e) {
                if (e.target.classList.contains('copy-path')) {
                    e.preventDefault();
                    copyToClipboard(e.target.dataset.path);
                }
            });
        });
    </script>
</body>
</html>
'''

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

    duplicate_groups = {k for k, v in hash_groups.items() if len(v) > 1}

    # Build table data as JSON for efficient JavaScript processing
    table_data = []
    for hash_val, group in hash_groups.items():
        is_duplicate = hash_val in duplicate_groups
        for row in group:
            filename, path, hash_value, size_bytes, scan_date = row
            size_formatted = format_file_size(size_bytes)
            size_category = get_size_category(size_bytes)
            table_data.append({
                'filename': filename,
                'path': path,
                'hash': hash_value,
                'size': size_formatted,
                'sizeCategory': size_category,
                'isDuplicate': is_duplicate
            })

    # Serialize table data to JSON with minimal overhead
    table_data_json = json.dumps(table_data, separators=(',', ':'), ensure_ascii=False)

    # Render template
    template = Template(HTML_TEMPLATE)
    html = template.render(
        total_files=len(records),
        scan_date=scan_date_display,
        table_data_json=table_data_json
    )

    # Ensure output directory exists
    dir_path = os.path.dirname(output_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"HTML report generated in {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a file hash HTML report.")
    parser.add_argument("--report", required=True, help="Output HTML file path")

    args = parser.parse_args()

    generate_html_report(args.report)
