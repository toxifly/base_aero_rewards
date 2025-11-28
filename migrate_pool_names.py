"""
Migrate old CSV snapshots to use proper pool names instead of addresses.

For pools where the name is just an address (CL pools), this script
looks up token0 and token1 symbols and constructs a name like CL-USDC/WETH.
"""

import csv
import sys
from pathlib import Path
from typing import List

from main import _token_symbol, _web3


def migrate_csv(csv_path: Path, dry_run: bool = False) -> int:
    """
    Update pool names in a CSV file.
    Returns the number of rows updated.
    """
    rows: List[dict] = []
    updated = 0

    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            name = row.get("name", "").strip()
            # Check if name looks like an address
            if name.startswith("0x") and len(name) == 42:
                token0 = row.get("token0", "")
                token1 = row.get("token1", "")
                if token0 and token1:
                    t0_sym = _token_symbol(token0)
                    t1_sym = _token_symbol(token1)
                    new_name = f"CL-{t0_sym}/{t1_sym}"
                    print(f"  {name[:10]}... -> {new_name}")
                    row["name"] = new_name
                    updated += 1
            rows.append(row)

    if not dry_run and updated > 0:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL, escapechar="\\")
            writer.writeheader()
            writer.writerows(rows)

    return updated


def main():
    dry_run = "--dry-run" in sys.argv

    # Find all pool CSV files
    csv_files = sorted(Path(".").glob("pools*.csv"), key=lambda p: p.stat().st_mtime)

    if not csv_files:
        print("No pools CSV files found.")
        return

    print(f"Found {len(csv_files)} CSV files")
    if dry_run:
        print("DRY RUN - no files will be modified\n")

    # Force web3 connection before processing
    print("Connecting to RPC...")
    _web3()
    print("Connected.\n")

    total_updated = 0
    for csv_path in csv_files:
        print(f"\nProcessing {csv_path.name}...")
        updated = migrate_csv(csv_path, dry_run=dry_run)
        total_updated += updated
        if updated:
            action = "would update" if dry_run else "updated"
            print(f"  {action} {updated} pool names")
        else:
            print("  no changes needed")

    print(f"\n{'Would update' if dry_run else 'Updated'} {total_updated} pool names total")


if __name__ == "__main__":
    main()
