from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.statcast_importer import import_statcast_cache


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Baseball Savant Statcast leaderboards for Strikers")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--min-pa", type=int, default=25)
    parser.add_argument("--min-bbe", type=int, default=15)
    args = parser.parse_args()

    print(f"Importing Statcast data for {args.season}...")
    print("This may take a few minutes. Existing predictions remain unchanged.")
    try:
        result = import_statcast_cache(args.season, args.min_pa, args.min_bbe)
    except Exception as exc:
        print(f"\nImport failed: {exc}", file=sys.stderr)
        return 1
    print("\nImport complete:")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
