# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.1.0",
# ]
# ///
"""
Save key-value pairs to the _user_config table in DuckDB.

Usage:
    uv run save_config.py --set key1=value1 --set key2=value2

Used by onboarding flow to persist user preferences without ad-hoc bash commands.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).parent))
from _log import log

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd()))
DATA_DIR = PROJECT_DIR / ".apify_plugin" / "data"
DB_PATH = DATA_DIR / "datasets.duckdb"


def main():
    parser = argparse.ArgumentParser(description="Save config key-value pairs to DuckDB")
    parser.add_argument("--set", dest="pairs", action="append", required=True,
                        help="Key=value pair to save (can repeat)")
    args = parser.parse_args()

    # Parse key=value pairs
    config = {}
    for pair in args.pairs:
        if "=" not in pair:
            print(json.dumps({"error": f"Invalid pair (missing '='): {pair}"}))
            sys.exit(1)
        key, _, value = pair.partition("=")
        config[key.strip()] = value.strip()

    if not config:
        print(json.dumps({"error": "No config pairs provided"}))
        sys.exit(1)

    # Ensure data dir exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(DB_PATH))

    # Ensure table exists
    con.execute("""
        CREATE TABLE IF NOT EXISTS _user_config (
            key VARCHAR PRIMARY KEY,
            value VARCHAR,
            updated_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    now = datetime.now(timezone.utc).isoformat()
    for key, value in config.items():
        con.execute("""
            INSERT INTO _user_config (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
        """, [key, value, now])

    con.close()

    log("save_config", f"saved {len(config)} keys: {list(config.keys())}")
    print(json.dumps({"status": "saved", "keys": list(config.keys())}))


if __name__ == "__main__":
    main()
