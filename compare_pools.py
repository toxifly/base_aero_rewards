import argparse
import csv
from pathlib import Path
from typing import Dict, Iterable, List, Optional


def _parse_number(value: Optional[str]):
    """
    Best-effort numeric parsing; returns float or int when possible.
    """
    if value is None:
        return value
    text = str(value).strip()
    if text == "":
        return value
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return value


def load_pools(csv_path: Path) -> List[dict]:
    """
    Load pools CSV and coerce numeric fields for easier downstream use.
    """
    rows: List[dict] = []
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            coerced = {k: _parse_number(v) for k, v in row.items()}
            rows.append(coerced)
    return rows


def _load_votes(csv_path: Path) -> Dict[str, dict]:
    """
    Minimal view of votes per pool keyed by address.
    """
    votes: Dict[str, dict] = {}
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("name") or "").strip()
            if name.upper() == "TOTAL":
                continue
            address = (row.get("address") or "").strip()
            if not address:
                continue

            def _as_float(val):
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return 0.0

            votes[address.lower()] = {
                "address": address,
                "name": name or address,
                "votes": _as_float(row.get("votes")),
                "vote_pct": _as_float(row.get("vote_pct")) if row.get("vote_pct") not in (None, "") else None,
            }
    return votes


def find_latest_csvs(limit: int = 2) -> List[Path]:
    """
    Return up to `limit` CSV files sorted by modified time (newest first).
    Prefers timestamped snapshots (pools_*.csv) but falls back to pools.csv.
    """
    candidates = sorted(Path(".").glob("pools_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    latest_plain = Path("pools.csv")
    if latest_plain.exists():
        candidates.append(latest_plain)

    seen = set()
    unique: List[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
        if len(unique) >= limit:
            break
    return unique


def compare_vote_changes(current_path: Path, previous_path: Path, top_n: Optional[int] = None) -> List[dict]:
    """
    Compare votes between two CSV snapshots.
    """
    current = _load_votes(current_path)
    previous = _load_votes(previous_path)
    addresses = set(current) | set(previous)
    changes: List[dict] = []

    for addr in addresses:
        curr_entry = current.get(addr)
        prev_entry = previous.get(addr)
        curr_votes = curr_entry["votes"] if curr_entry else 0.0
        prev_votes = prev_entry["votes"] if prev_entry else 0.0
        delta = curr_votes - prev_votes
        delta_pct = (delta / prev_votes * 100) if prev_votes else None
        name = (curr_entry or prev_entry or {}).get("name", addr)

        changes.append(
            {
                "address": curr_entry["address"] if curr_entry else (prev_entry["address"] if prev_entry else addr),
                "name": name,
                "current_votes": curr_votes,
                "previous_votes": prev_votes,
                "delta_votes": delta,
                "delta_pct": delta_pct,
            }
        )

    changes.sort(key=lambda x: abs(x["delta_votes"]), reverse=True)
    return changes[:top_n] if top_n else changes


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compare vote changes between two pools CSV snapshots.")
    parser.add_argument("--current", type=Path, help="Path to the newer CSV file")
    parser.add_argument("--previous", type=Path, help="Path to the older CSV file")
    parser.add_argument("--top", type=int, default=20, help="How many entries to print (default: 20)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    current_path = args.current
    previous_path = args.previous
    if current_path is None or previous_path is None:
        latest_two = find_latest_csvs(2)
        if len(latest_two) < 2:
            print("Need at least two CSV snapshots to compare.")
            return 1
        current_path = current_path or latest_two[0]
        previous_path = previous_path or latest_two[1]

    if not current_path.exists() or not previous_path.exists():
        print("Provided CSV paths do not exist.")
        return 1

    changes = compare_vote_changes(current_path, previous_path, top_n=args.top)
    print(f"Comparing {current_path.name} (current) vs {previous_path.name} (previous)")
    for entry in changes:
        delta_pct = entry["delta_pct"]
        delta_pct_str = f"{delta_pct:+.2f}%" if delta_pct is not None else "n/a"
        print(
            f"{entry['name']}: "
            f"{entry['previous_votes']:.2f} -> {entry['current_votes']:.2f} "
            f"({entry['delta_votes']:+.2f}, {delta_pct_str})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
