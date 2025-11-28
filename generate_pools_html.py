import json
from pathlib import Path
from typing import Optional

from compare_pools import compare_vote_changes, find_latest_csvs, load_pools


def _previous_snapshot(current_csv: Path) -> Optional[Path]:
    """
    Find the next-most-recent snapshot relative to `current_csv`.
    """
    history = find_latest_csvs(50)
    for idx, path in enumerate(history):
        if path.resolve() == current_csv.resolve() and idx + 1 < len(history):
            return history[idx + 1]
    return history[1] if len(history) >= 2 else None


def generate_html(source_csv: Optional[str | Path] = None):
    """
    Build pools.html from the latest snapshot (or a provided CSV).
    Also includes vote-change data between the two most recent snapshots.
    """
    if source_csv:
        current_csv = Path(source_csv)
    else:
        latest = find_latest_csvs(1)
        if not latest:
            print("Error: no pools CSV files found.")
            return
        current_csv = latest[0]

    if not current_csv.exists():
        print(f"Error: {current_csv} not found.")
        return

    pools_raw = load_pools(current_csv)
    pools_data = [row for row in pools_raw if str(row.get("name", "")).strip().upper() != "TOTAL"]

    previous_csv = _previous_snapshot(current_csv)
    vote_changes = []
    comparison_meta = {"current": current_csv.name, "previous": previous_csv.name if previous_csv else None}

    if previous_csv:
        # Show all vote deltas (sorted by absolute change) so the table includes every pool.
        vote_changes = compare_vote_changes(current_csv, previous_csv, top_n=None)
    else:
        print("Warning: only one CSV snapshot found; skipping vote change comparison.")

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aerodrome Pools Analysis</title>
    <style>
        :root {{
            --bg: #0a0e1a;
            --panel: #0f1525;
            --panel-alt: #151b2e;
            --panel-hover: #1a2236;
            --accent: #00d4ff;
            --accent-dim: rgba(0, 212, 255, 0.15);
            --accent-2: #7c3aed;
            --text: #f1f5f9;
            --muted: #64748b;
            --positive: #22c55e;
            --negative: #ef4444;
            --border: #1e293b;
            --glow: rgba(0, 212, 255, 0.1);
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg);
            background-image:
                radial-gradient(ellipse 80% 50% at 50% -20%, var(--glow), transparent),
                radial-gradient(ellipse 60% 40% at 100% 0%, rgba(124, 58, 237, 0.08), transparent);
            color: var(--text);
            min-height: 100vh;
            padding: 24px 16px 48px;
            line-height: 1.5;
        }}
        h1 {{
            text-align: center;
            font-size: 1.75rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 8px;
            letter-spacing: -0.02em;
        }}
        .subhead {{
            text-align: center;
            color: var(--muted);
            margin-bottom: 24px;
            font-size: 0.875rem;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .layout {{
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        .card {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            backdrop-filter: blur(8px);
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
        }}
        .stat {{
            display: flex;
            flex-direction: column;
            gap: 4px;
            background: var(--panel-alt);
            padding: 14px 16px;
            border-radius: 10px;
            border: 1px solid var(--border);
            transition: border-color 0.2s, background 0.2s;
        }}
        .stat:hover {{
            border-color: var(--accent);
            background: var(--panel-hover);
        }}
        .stat-label {{ color: var(--muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
        .stat-value {{ font-size: 1.125rem; font-weight: 600; color: var(--text); word-break: break-word; }}
        .stat-value.positive {{ color: var(--positive); }}
        .stat-value.negative {{ color: var(--negative); }}
        .chip {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            background: var(--accent-dim);
            color: var(--accent);
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 500;
            font-family: 'Roboto Mono', monospace;
        }}
        .controls {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 12px;
        }}
        .control-group {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        label {{ color: var(--muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
        input {{
            background: var(--panel-alt);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 10px 12px;
            border-radius: 8px;
            outline: none;
            font-size: 0.875rem;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}
        input:focus {{
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-dim);
        }}
        input::placeholder {{ color: var(--muted); }}
        .table-wrapper {{
            overflow-x: auto;
            margin: 0 -16px;
            padding: 0 16px;
        }}
        .table-card table {{
            width: 100%;
            min-width: 900px;
            border-collapse: collapse;
            margin-top: 12px;
            font-size: 0.875rem;
        }}
        th, td {{
            padding: 12px 10px;
            text-align: left;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }}
        th {{
            color: var(--muted);
            font-weight: 500;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            cursor: pointer;
            user-select: none;
            position: sticky;
            top: 0;
            background: var(--panel);
            z-index: 10;
            transition: color 0.2s;
        }}
        th:hover {{ color: var(--accent); }}
        th.sorted {{ color: var(--accent); }}
        th .sort-icon {{ opacity: 0.5; margin-left: 4px; }}
        th.sorted .sort-icon {{ opacity: 1; }}
        tbody tr {{
            transition: background 0.15s;
        }}
        tbody tr:hover {{ background: var(--panel-alt); }}
        tbody tr:nth-child(even) {{ background: rgba(255, 255, 255, 0.01); }}
        tbody tr:nth-child(even):hover {{ background: var(--panel-alt); }}
        td.name-cell {{
            font-weight: 500;
            color: var(--text);
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .metric-value {{
            font-family: 'Roboto Mono', monospace;
            font-size: 0.8rem;
            color: var(--muted);
        }}
        .positive {{ color: var(--positive) !important; }}
        .negative {{ color: var(--negative) !important; }}
        .muted {{ color: var(--muted); }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 4px;
        }}
        .card-title {{ font-size: 0.95rem; font-weight: 600; }}
        .small {{ font-size: 0.8rem; color: var(--muted); margin-top: 2px; }}
        .empty {{ color: var(--muted); text-align: center; padding: 24px 0; }}
        .row-count {{
            font-size: 0.75rem;
            color: var(--muted);
            padding: 8px 0;
        }}
        @media (max-width: 768px) {{
            body {{ padding: 16px 12px 32px; }}
            h1 {{ font-size: 1.5rem; }}
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .controls {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">
</head>
<body>
    <div class="layout">
        <div>
            <h1>Aerodrome Pools Analysis</h1>
            <div class="subhead">Snapshot: <span id="snapshotLabel" class="chip"></span> | Previous: <span id="comparisonLabel" class="chip"></span></div>
        </div>

        <div class="stats-grid">
            <div class="stat">
                <div class="stat-label">Total Pools</div>
                <div class="stat-value" id="totalPools">-</div>
            </div>
            <div class="stat">
                <div class="stat-label">Avg V/TVV</div>
                <div class="stat-value" id="avgVotesPerTVV">-</div>
            </div>
            <div class="stat">
                <div class="stat-label">Median V/TVV</div>
                <div class="stat-value" id="medianVotesPerTVV">-</div>
            </div>
            <div class="stat">
                <div class="stat-label">Top + Votes Change</div>
                <div class="stat-value" id="topPositiveChange">-</div>
            </div>
            <div class="stat">
                <div class="stat-label">Top - Votes Change</div>
                <div class="stat-value" id="topNegativeChange">-</div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <div>
                    <p class="card-title">Filter Pools</p>
                    <p class="small">Use vote share and efficiency bounds to slice the data quickly.</p>
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
        </div>

        <div class="card table-card">
            <div class="card-header">
                <div>
                    <p class="card-title">Pools + Vote Changes</p>
                    <p class="small">Efficiency metrics and vote deltas between snapshots. Click headers to sort.</p>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <span class="row-count" id="rowCount"></span>
                    <div class="chip" id="comparisonChip">Prev: {comparison_meta.get("previous") or "n/a"}</div>
                </div>
            </div>
            <div class="table-wrapper">
                <table id="poolsTable">
                    <thead>
                        <tr>
                            <th onclick="sortTable('name')" data-key="name">Pool<span class="sort-icon"></span></th>
                            <th onclick="sortTable('vote_pct')" data-key="vote_pct">Vote %<span class="sort-icon"></span></th>
                            <th onclick="sortTable('votes')" data-key="votes">Votes<span class="sort-icon"></span></th>
                            <th onclick="sortTable('previous_votes')" data-key="previous_votes">Prev<span class="sort-icon"></span></th>
                            <th onclick="sortTable('delta_votes')" data-key="delta_votes">Δ Votes<span class="sort-icon"></span></th>
                            <th onclick="sortTable('delta_pct')" data-key="delta_pct">Δ %<span class="sort-icon"></span></th>
                            <th onclick="sortTable('tvv')" data-key="tvv">TVV<span class="sort-icon"></span></th>
                            <th onclick="sortTable('votes_per_tvv')" data-key="votes_per_tvv">V/TVV<span class="sort-icon"></span></th>
                        </tr>
                    </thead>
                    <tbody id="tableBody"></tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const POOLS_DATA = {json.dumps(pools_data, default=str)};
        const VOTE_CHANGES = {json.dumps(vote_changes, default=str)};
        const COMPARISON_META = {json.dumps(comparison_meta)};

        const CHANGE_MAP = new Map();
        (VOTE_CHANGES || []).forEach(entry => {{
            const key = (entry.address || '').toLowerCase();
            if (key) CHANGE_MAP.set(key, entry);
        }});

        const TABLE_ROWS = (POOLS_DATA || []).map(pool => {{
            const change = CHANGE_MAP.get((pool.address || '').toLowerCase()) || {{}};
            return {{
                ...pool,
                previous_votes: change.previous_votes ?? null,
                delta_votes: change.delta_votes ?? null,
                delta_pct: change.delta_pct ?? null,
            }};
        }});

        let currentSort = {{ key: 'vote_pct', dir: 'desc' }};

        // Helper to check for valid finite numbers (handles Python nan/inf as strings)
        function isValidNumber(val) {{
            if (val === null || val === undefined) return false;
            if (typeof val === 'string') {{
                const lower = val.toLowerCase();
                if (lower === 'nan' || lower === 'inf' || lower === '-inf' || lower === 'infinity' || lower === '-infinity') return false;
            }}
            const num = Number(val);
            return !isNaN(num) && isFinite(num) && num > 0;
        }}

        const validPools = TABLE_ROWS.filter(p => isValidNumber(p.votes_per_tvv));
        const sortedVPT = [...validPools].sort((a, b) => Number(a.votes_per_tvv) - Number(b.votes_per_tvv));

        let globalMedianVotesPerTVV = 0;
        let globalAvgVotesPerTVV = 0;
        if (sortedVPT.length > 0) {{
            const mid = Math.floor(sortedVPT.length / 2);
            globalMedianVotesPerTVV = sortedVPT.length % 2 !== 0
                ? Number(sortedVPT[mid].votes_per_tvv)
                : (Number(sortedVPT[mid - 1].votes_per_tvv) + Number(sortedVPT[mid].votes_per_tvv)) / 2;
            const sum = sortedVPT.reduce((acc, p) => acc + Number(p.votes_per_tvv), 0);
            globalAvgVotesPerTVV = sum / sortedVPT.length;
        }}

        document.getElementById('totalPools').innerText = TABLE_ROWS.length;
        document.getElementById('avgVotesPerTVV').innerText = formatNumber(globalAvgVotesPerTVV, 1);
        document.getElementById('medianVotesPerTVV').innerText = formatNumber(globalMedianVotesPerTVV, 1);
        document.getElementById('snapshotLabel').innerText = COMPARISON_META.current || 'n/a';
        document.getElementById('comparisonLabel').innerText = COMPARISON_META.previous || 'n/a';

        function formatNumber(num, decimals = 2) {{
            if (num === null || num === undefined || isNaN(num)) return '-';
            return Number(num).toLocaleString(undefined, {{ minimumFractionDigits: decimals, maximumFractionDigits: decimals }});
        }}

        function renderTable() {{
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';

            const minVotesPerTVV = parseFloat(document.getElementById('minVotesPerTVV').value) || -Infinity;
            const maxVotesPerTVV = parseFloat(document.getElementById('maxVotesPerTVV').value) || Infinity;
            const minVotePct = parseFloat(document.getElementById('minVotePct').value) || -Infinity;
            const maxVotePct = parseFloat(document.getElementById('maxVotePct').value) || Infinity;
            const searchName = (document.getElementById('searchName').value || '').toLowerCase();

            let filteredData = TABLE_ROWS.filter(pool => {{
                const vpt = pool.votes_per_tvv || 0;
                const vp = pool.vote_pct || 0;
                const name = (pool.name || '').toLowerCase();

                return vpt >= minVotesPerTVV &&
                       vpt <= maxVotesPerTVV &&
                       vp >= minVotePct &&
                       vp <= maxVotePct &&
                       name.includes(searchName);
            }});

            filteredData.sort((a, b) => {{
                let valA = a[currentSort.key];
                let valB = b[currentSort.key];

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
                const vpt = isValidNumber(pool.votes_per_tvv) ? Number(pool.votes_per_tvv) : null;
                let vptClass = 'muted';
                if (vpt !== null && globalMedianVotesPerTVV > 0) {{
                    if (vpt > globalMedianVotesPerTVV * 1.25) {{
                        vptClass = 'negative';
                    }} else if (vpt < globalMedianVotesPerTVV * 0.75) {{
                        vptClass = 'positive';
                    }}
                }}

                const deltaVotes = pool.delta_votes;
                const deltaPct = pool.delta_pct;
                const deltaClass = deltaVotes > 0 ? 'positive' : (deltaVotes < 0 ? 'negative' : 'muted');
                const deltaPctDisplay = (deltaPct === null || deltaPct === undefined || isNaN(deltaPct))
                    ? 'n/a'
                    : `${{deltaPct > 0 ? '+' : ''}}${{Number(deltaPct).toFixed(2)}}%`;

                tr.innerHTML = `
                    <td class="name-cell" title="${{pool.name}}">${{pool.name}}</td>
                    <td class="metric-value">${{formatNumber(pool.vote_pct, 4)}}%</td>
                    <td class="metric-value">${{formatNumber(pool.votes, 0)}}</td>
                    <td class="metric-value">${{formatNumber(pool.previous_votes, 0)}}</td>
                    <td class="metric-value ${{deltaClass}}">${{formatNumber(deltaVotes, 0)}}</td>
                    <td class="metric-value ${{deltaClass}}">${{deltaPctDisplay}}</td>
                    <td class="metric-value">$${{formatNumber(pool.tvv, 0)}}</td>
                    <td class="metric-value ${{vptClass}}">${{vpt !== null ? formatNumber(vpt, 1) : '-'}}</td>
                `;
                tbody.appendChild(tr);
            }});

            // Update row count
            document.getElementById('rowCount').innerText = `${{filteredData.length}} pools`;

            // Update sort indicators
            document.querySelectorAll('th[data-key]').forEach(th => {{
                th.classList.remove('sorted');
                const icon = th.querySelector('.sort-icon');
                icon.textContent = '';
            }});
            const sortedTh = document.querySelector(`th[data-key="${{currentSort.key}}"]`);
            if (sortedTh) {{
                sortedTh.classList.add('sorted');
                sortedTh.querySelector('.sort-icon').textContent = currentSort.dir === 'desc' ? ' ↓' : ' ↑';
            }}
        }}

        function sortTable(key) {{
            if (currentSort.key === key) {{
                currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc';
            }} else {{
                currentSort.key = key;
                currentSort.dir = 'desc';
            }}
            renderTable();
        }}

        function populateChangeStats() {{
            const chip = document.getElementById('comparisonChip');
            if (!VOTE_CHANGES || VOTE_CHANGES.length === 0 || !COMPARISON_META.previous) {{
                chip.innerText = 'Prev: n/a';
                document.getElementById('topPositiveChange').innerText = '-';
                document.getElementById('topNegativeChange').innerText = '-';
                return;
            }}

            chip.innerText = `Prev: ${{COMPARISON_META.previous}}`;

            let topPositive = null;
            let topNegative = null;

            VOTE_CHANGES.forEach(entry => {{
                if (entry.delta_votes > 0 && (!topPositive || entry.delta_votes > topPositive.delta_votes)) {{
                    topPositive = entry;
                }}
                if (entry.delta_votes < 0 && (!topNegative || entry.delta_votes < topNegative.delta_votes)) {{
                    topNegative = entry;
                }}
            }});

            document.getElementById('topPositiveChange').innerText = topPositive ? `${{topPositive.name}} ( +${{formatNumber(topPositive.delta_votes, 2)}} )` : '-';
            document.getElementById('topNegativeChange').innerText = topNegative ? `${{topNegative.name}} ( ${{formatNumber(topNegative.delta_votes, 2)}} )` : '-';
        }}

        populateChangeStats();
        renderTable();
    </script>
</body>
</html>
    """

    with open("pools.html", "w") as f:
        f.write(html_content)
    print(f"Successfully generated pools.html using {current_csv.name}")


if __name__ == "__main__":
    generate_html()
