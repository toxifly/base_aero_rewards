import csv
import json
import os

def generate_html():
    # Read pools.csv
    pools_data = []
    try:
        with open('pools.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert numeric fields to appropriate types for JSON
                for key, value in row.items():
                    try:
                        if '.' in value:
                            row[key] = float(value)
                        else:
                            row[key] = int(value)
                    except (ValueError, TypeError):
                        pass # Keep as string if not a number
                pools_data.append(row)
    except FileNotFoundError:
        print("Error: pools.csv not found.")
        return

    # HTML Template
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aerodrome Pools Analysis</title>
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            background-color: #0f172a;
            color: #e2e8f0;
            margin: 0;
            padding: 20px;
        }}
        h1 {{
            text-align: center;
            color: #38bdf8;
            margin-bottom: 30px;
        }}
        .stats-bar {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 20px;
            background: #1e293b;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        .stat-item {{
            text-align: center;
        }}
        .stat-label {{
            font-size: 0.85em;
            color: #94a3b8;
            margin-bottom: 5px;
        }}
        .stat-value {{
            font-size: 1.2em;
            font-weight: 600;
            color: #e2e8f0;
            font-family: 'Roboto Mono', monospace;
        }}
        .controls {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            justify-content: center;
            margin-bottom: 20px;
            background: #1e293b;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        .control-group {{
            display: flex;
            flex-direction: column;
            gap: 5px;
        }}
        label {{
            font-size: 0.9em;
            color: #94a3b8;
        }}
        input {{
            background: #334155;
            border: 1px solid #475569;
            color: white;
            padding: 8px;
            border-radius: 5px;
            outline: none;
        }}
        input:focus {{
            border-color: #38bdf8;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: #1e293b;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #334155;
        }}
        th {{
            background-color: #0f172a;
            color: #38bdf8;
            cursor: pointer;
            user-select: none;
            position: sticky;
            top: 0;
        }}
        th:hover {{
            background-color: #1e293b;
        }}
        tr:hover {{
            background-color: #334155;
        }}
        .overpaid {{
            color: #f87171; /* Red - High Votes/TVV */
        }}
        .underpaid {{
            color: #4ade80; /* Green - Low Votes/TVV */
        }}
        .neutral {{
            color: #e2e8f0;
        }}
        .metric-value {{
            font-family: 'Roboto Mono', monospace;
        }}
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Roboto+Mono&display=swap" rel="stylesheet">
</head>
<body>

    <h1>Aerodrome Pools Analysis</h1>

    <div class="stats-bar">
        <div class="stat-item">
            <div class="stat-label">Total Pools</div>
            <div class="stat-value" id="totalPools">-</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Median Votes/TVV</div>
            <div class="stat-value" id="medianVotesPerTVV">-</div>
        </div>
    </div>

    <div class="controls">
        <div class="control-group">
            <label>Min Votes/TVV</label>
            <input type="number" id="minVotesPerTVV" placeholder="Min" oninput="renderTable()">
        </div>
        <div class="control-group">
            <label>Max Votes/TVV</label>
            <input type="number" id="maxVotesPerTVV" placeholder="Max" oninput="renderTable()">
        </div>
        <div class="control-group">
            <label>Min Vote %</label>
            <input type="number" id="minVotePct" placeholder="Min %" step="0.01" oninput="renderTable()">
        </div>
        <div class="control-group">
            <label>Max Vote %</label>
            <input type="number" id="maxVotePct" placeholder="Max %" step="0.01" oninput="renderTable()">
        </div>
        <div class="control-group">
            <label>Search Name</label>
            <input type="text" id="searchName" placeholder="Pool Name" oninput="renderTable()">
        </div>
    </div>

    <table id="poolsTable">
        <thead>
            <tr>
                <th onclick="sortTable('name')">Name</th>
                <th onclick="sortTable('vote_pct')">Vote %</th>
                <th onclick="sortTable('votes')">Votes</th>
                <th onclick="sortTable('tvv')">TVV ($)</th>
                <th onclick="sortTable('votes_per_tvv')">Votes / TVV</th>
            </tr>
        </thead>
        <tbody id="tableBody">
            <!-- Rows will be populated by JS -->
        </tbody>
    </table>

    <script>
        const POOLS_DATA = {json.dumps(pools_data)};
        let currentSort = {{ key: 'vote_pct', dir: 'desc' }};
        
        // Calculate global stats (Median)
        const validPools = POOLS_DATA
            .filter(p => p.votes_per_tvv !== null && p.votes_per_tvv !== undefined && !isNaN(p.votes_per_tvv))
            .map(p => p.votes_per_tvv)
            .sort((a, b) => a - b);
            
        let globalMedianVotesPerTVV = 0;
        if (validPools.length > 0) {{
            const mid = Math.floor(validPools.length / 2);
            globalMedianVotesPerTVV = validPools.length % 2 !== 0 
                ? validPools[mid] 
                : (validPools[mid - 1] + validPools[mid]) / 2;
        }}

        document.getElementById('totalPools').innerText = POOLS_DATA.length;
        document.getElementById('medianVotesPerTVV').innerText = formatNumber(globalMedianVotesPerTVV);

        function formatNumber(num, decimals = 2) {{
            if (num === null || num === undefined || isNaN(num)) return '-';
            return num.toLocaleString(undefined, {{ minimumFractionDigits: decimals, maximumFractionDigits: decimals }});
        }}

        function renderTable() {{
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';

            const minVotesPerTVV = parseFloat(document.getElementById('minVotesPerTVV').value) || -Infinity;
            const maxVotesPerTVV = parseFloat(document.getElementById('maxVotesPerTVV').value) || Infinity;
            const minVotePct = parseFloat(document.getElementById('minVotePct').value) || -Infinity;
            const maxVotePct = parseFloat(document.getElementById('maxVotePct').value) || Infinity;
            const searchName = document.getElementById('searchName').value.toLowerCase();

            let filteredData = POOLS_DATA.filter(pool => {{
                const vpt = pool.votes_per_tvv || 0;
                const vp = pool.vote_pct || 0;
                const name = (pool.name || '').toLowerCase();

                return vpt >= minVotesPerTVV &&
                       vpt <= maxVotesPerTVV &&
                       vp >= minVotePct &&
                       vp <= maxVotePct &&
                       name.includes(searchName);
            }});

            // Sort
            filteredData.sort((a, b) => {{
                let valA = a[currentSort.key];
                let valB = b[currentSort.key];

                // Handle nulls/undefined
                if (valA === undefined || valA === null) valA = -Infinity;
                if (valB === undefined || valB === null) valB = -Infinity;

                if (typeof valA === 'string') valA = valA.toLowerCase();
                if (typeof valB === 'string') valB = valB.toLowerCase();

                if (valA < valB) return currentSort.dir === 'asc' ? -1 : 1;
                if (valA > valB) return currentSort.dir === 'asc' ? 1 : -1;
                return 0;
            }});

            filteredData.forEach(pool => {{
                const tr = document.createElement('tr');
                
                // Color coding logic based on global Median
                // Overpaid: > 1.25 * Median
                // Underpaid: < 0.75 * Median
                
                let vptClass = 'neutral';
                if (pool.votes_per_tvv > globalMedianVotesPerTVV * 1.25) {{
                    vptClass = 'overpaid';
                }} else if (pool.votes_per_tvv < globalMedianVotesPerTVV * 0.75 && pool.votes_per_tvv > 0) {{
                    vptClass = 'underpaid';
                }}

                tr.innerHTML = `
                    <td>${{pool.name}}</td>
                    <td class="metric-value">${{formatNumber(pool.vote_pct, 4)}}%</td>
                    <td class="metric-value">${{formatNumber(pool.votes, 0)}}</td>
                    <td class="metric-value">$${{formatNumber(pool.tvv)}}</td>
                    <td class="metric-value ${{vptClass}}">${{formatNumber(pool.votes_per_tvv)}}</td>
                `;
                tbody.appendChild(tr);
            }});
        }}

        function sortTable(key) {{
            if (currentSort.key === key) {{
                currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc';
            }} else {{
                currentSort.key = key;
                currentSort.dir = 'desc'; // Default to desc for numbers usually
            }}
            renderTable();
        }}

        // Initial render
        renderTable();
    </script>
</body>
</html>
    """

    with open('pools.html', 'w') as f:
        f.write(html_content)
    print("Successfully generated pools.html")

if __name__ == "__main__":
    generate_html()
