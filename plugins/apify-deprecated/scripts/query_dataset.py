# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.1.0",
# ]
# ///
"""
Query DuckDB or JSON files directly.

Provides a safe interface for Claude to query landed data without
loading full datasets into context.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import duckdb

def _resolve_project_dir() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    cwd = Path.cwd()
    if (cwd / ".apify-plugin").exists():
        return cwd
    print(json.dumps({"error": "CLAUDE_PROJECT_DIR not set and .apify-plugin/ not found in cwd", "cwd": str(cwd)}), file=sys.stderr)
    sys.exit(1)

PROJECT_DIR = _resolve_project_dir()
DATA_DIR = PROJECT_DIR / ".apify-plugin" / "data"
DB_PATH = DATA_DIR / "datasets.duckdb"


def query_duckdb(sql: str, limit: int = 100) -> dict:
    """Execute SQL query against DuckDB."""
    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        # Add LIMIT if not present and not a metadata query
        sql_upper = sql.strip().upper()
        if "LIMIT" not in sql_upper and sql_upper.startswith("SELECT"):
            sql = f"{sql.rstrip(';')} LIMIT {limit}"

        result = con.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        # Convert to list of dicts
        data = []
        for row in rows:
            row_dict = {}
            for col, val in zip(columns, row):
                # Handle non-JSON-serializable types
                if isinstance(val, (bytes, memoryview)):
                    row_dict[col] = str(val)
                else:
                    row_dict[col] = val
            data.append(row_dict)

        return {
            "columns": columns,
            "row_count": len(data),
            "data": data,
            "truncated": len(data) >= limit,
        }

    except Exception as e:
        return {"error": str(e)}
    finally:
        con.close()


def list_tables() -> dict:
    """List all tables in DuckDB with row counts."""
    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        tables = con.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
        """).fetchall()

        table_info = []
        for (name,) in tables:
            try:
                count = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                cols = con.execute(f'DESCRIBE "{name}"').fetchall()
                table_info.append({
                    "name": name,
                    "row_count": count,
                    "columns": [{"name": c[0], "type": c[1]} for c in cols],
                })
            except Exception:
                table_info.append({"name": name, "error": "Could not describe"})

        return {"tables": table_info, "count": len(table_info)}

    except Exception as e:
        return {"error": str(e)}
    finally:
        con.close()


def query_catalog() -> dict:
    """Query the _catalog table for known actor output schemas."""
    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        results = con.execute("""
            SELECT actor_slug, output_fields, last_updated
            FROM _catalog
            ORDER BY last_updated DESC
        """).fetchall()

        catalog = []
        for slug, fields, updated in results:
            field_data = json.loads(fields) if isinstance(fields, str) else fields
            catalog.append({
                "actor_slug": slug,
                "field_count": len(field_data) if isinstance(field_data, dict) else 0,
                "fields": field_data,
                "last_updated": str(updated),
            })

        return {"catalog": catalog, "count": len(catalog)}

    except Exception as e:
        return {"error": str(e)}
    finally:
        con.close()


def query_jsonl(file_path: str, jq_filter: str = None, limit: int = 100) -> dict:
    """Query a JSONL file, optionally with field filtering."""
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    results = []
    total = 0

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            if len(results) >= limit:
                continue

            try:
                item = json.loads(line)

                if jq_filter:
                    # Simple field filtering: "field1,field2,field3"
                    fields = [f.strip() for f in jq_filter.split(",")]
                    filtered = {k: item.get(k) for k in fields if k in item}
                    results.append(filtered)
                else:
                    results.append(item)

            except json.JSONDecodeError:
                continue

    return {
        "file": str(path),
        "total_rows": total,
        "returned": len(results),
        "truncated": total > limit,
        "data": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Query datasets")
    sub = parser.add_subparsers(dest="command", required=True)

    # sql
    sql_parser = sub.add_parser("sql", help="Run SQL query against DuckDB")
    sql_parser.add_argument("query", help="SQL query string")
    sql_parser.add_argument("--limit", type=int, default=100, help="Max rows to return")

    # tables
    sub.add_parser("tables", help="List all DuckDB tables")

    # catalog
    sub.add_parser("catalog", help="Show known actor output schemas")

    # jsonl
    jsonl_parser = sub.add_parser("jsonl", help="Query a JSONL file")
    jsonl_parser.add_argument("file", help="Path to JSONL file")
    jsonl_parser.add_argument("--fields", help="Comma-separated field names to extract")
    jsonl_parser.add_argument("--limit", type=int, default=100, help="Max rows to return")

    args = parser.parse_args()

    if args.command == "sql":
        result = query_duckdb(args.query, args.limit)
    elif args.command == "tables":
        result = list_tables()
    elif args.command == "catalog":
        result = query_catalog()
    elif args.command == "jsonl":
        result = query_jsonl(args.file, args.fields, args.limit)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
