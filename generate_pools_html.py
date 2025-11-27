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
            --bg: #0c1024;
            --panel: #11162b;
            --panel-alt: #161c33;
            --accent: #5be3ff;
            --accent-2: #8f9bff;
            --text: #e8edf6;
            --muted: #98a0b5;
            --positive: #4ade80;
            --negative: #f87171;
            --border: #1f2941;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: 'Inter', sans-serif;
            background: radial-gradient(120% 120% at 20% 20%, rgba(91, 227, 255, 0.08), transparent),
                        radial-gradient(100% 100% at 80% 0%, rgba(143, 155, 255, 0.08), transparent),
                        var(--bg);
            color: var(--text);
            margin: 0;
            padding: 32px 18px 64px;
            line-height: 1.4;
        }}
        h1 {{
            text-align: center;
            color: var(--accent);
            margin-bottom: 12px;
            letter-spacing: 0.5px;
        }}
        .subhead {{
            text-align: center;
            color: var(--muted);
            margin-bottom: 28px;
            font-size: 0.95rem;
        }}
        .layout {{
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 18px;
        }}
        .card {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 14px;
            box-shadow: 0 14px 40px rgba(0, 0, 0, 0.18);
            padding: 18px 20px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
        }}
        .stat {{
            display: flex;
            flex-direction: column;
            gap: 4px;
            background: var(--panel-alt);
            padding: 12px 14px;
            border-radius: 10px;
            border: 1px solid var(--border);
        }}
        .stat-label {{ color: var(--muted); font-size: 0.85rem; }}
        .stat-value {{ font-size: 1.25rem; font-weight: 600; color: var(--text); }}
        .chip {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 10px;
            background: rgba(91, 227, 255, 0.12);
            color: var(--accent);
            border-radius: 999px;
            border: 1px solid rgba(91, 227, 255, 0.25);
            font-size: 0.85rem;
        }}
        .controls {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
        }}
        .control-group {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        label {{ color: var(--muted); font-size: 0.85rem; }}
        input {{
            background: var(--panel-alt);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 9px 10px;
            border-radius: 8px;
            outline: none;
        }}
        input:focus {{ border-color: var(--accent); }}
        .table-card table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th, td {{
            padding: 11px 10px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            color: var(--accent);
            cursor: pointer;
            user-select: none;
            position: sticky;
            top: 0;
            background: var(--panel);
        }}
        th:hover {{ background: var(--panel-alt); }}
        tr:hover td {{ background: rgba(255, 255, 255, 0.03); }}
        .metric-value {{ font-family: 'Roboto Mono', monospace; }}
        .positive {{ color: var(--positive); }}
        .negative {{ color: var(--negative); }}
        .muted {{ color: var(--muted); }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 6px;
        }}
        .card-title {{ margin: 0; font-size: 1.05rem; }}
        .small {{ font-size: 0.9rem; color: var(--muted); margin: 4px 0 0; }}
        .empty {{ color: var(--muted); text-align: center; padding: 12px 0; }}
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Roboto+Mono&display=swap" rel="stylesheet">
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
                <div class="stat-label">Median Votes/TVV</div>
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
                    <p class="small">Single view with efficiency metrics and vote deltas between snapshots.</p>
                </div>
                <div class="chip" id="comparisonChip">Prev: {comparison_meta.get("previous") or "n/a"}</div>
            </div>
            <table id="poolsTable">
                <thead>
                    <tr>
                        <th onclick="sortTable('name')">Name</th>
                        <th onclick="sortTable('vote_pct')">Vote %</th>
                        <th onclick="sortTable('votes')">Votes</th>
                        <th onclick="sortTable('previous_votes')">Prev Votes</th>
                        <th onclick="sortTable('delta_votes')">Δ Votes</th>
                        <th onclick="sortTable('delta_pct')">Δ %</th>
                        <th onclick="sortTable('tvv')">TVV ($)</th>
                        <th onclick="sortTable('votes_per_tvv')">Votes / TVV</th>
                    </tr>
                </thead>
                <tbody id="tableBody"></tbody>
            </table>
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

        const validPools = TABLE_ROWS
            .filter(p => p.votes_per_tvv !== null && p.votes_per_tvv !== undefined && !isNaN(p.votes_per_tvv));
        const sortedVPT = [...validPools].sort((a, b) => a.votes_per_tvv - b.votes_per_tvv);

        let globalMedianVotesPerTVV = 0;
        if (sortedVPT.length > 0) {{
            const mid = Math.floor(sortedVPT.length / 2);
            globalMedianVotesPerTVV = sortedVPT.length % 2 !== 0
                ? sortedVPT[mid].votes_per_tvv
                : (sortedVPT[mid - 1].votes_per_tvv + sortedVPT[mid]) / 2;
        }}

        document.getElementById('totalPools').innerText = TABLE_ROWS.length;
        document.getElementById('medianVotesPerTVV').innerText = formatNumber(globalMedianVotesPerTVV);
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
                let vptClass = 'muted';
                if (pool.votes_per_tvv > globalMedianVotesPerTVV * 1.25) {{
                    vptClass = 'negative';
                }} else if (pool.votes_per_tvv < globalMedianVotesPerTVV * 0.75 && pool.votes_per_tvv > 0) {{
                    vptClass = 'positive';
                }}

                const deltaVotes = pool.delta_votes;
                const deltaPct = pool.delta_pct;
                const deltaClass = deltaVotes > 0 ? 'positive' : (deltaVotes < 0 ? 'negative' : 'muted');
                const deltaPctDisplay = (deltaPct === null || deltaPct === undefined || isNaN(deltaPct))
                    ? 'n/a'
                    : `${{deltaPct > 0 ? '+' : ''}}${{Number(deltaPct).toFixed(2)}}%`;

                tr.innerHTML = `
                    <td>${{pool.name}}</td>
                    <td class="metric-value">${{formatNumber(pool.vote_pct, 4)}}%</td>
                    <td class="metric-value">${{formatNumber(pool.votes, 0)}}</td>
                    <td class="metric-value">${{formatNumber(pool.previous_votes, 0)}}</td>
                    <td class="metric-value ${{deltaClass}}">${{formatNumber(deltaVotes, 2)}}</td>
                    <td class="metric-value ${{deltaClass}}">${{deltaPctDisplay}}</td>
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
