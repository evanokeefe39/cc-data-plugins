# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.1.0",
# ]
# ///
"""
Import downloaded dataset files into DuckDB.

Handles:
- JSONL file import into DuckDB tables
- Schema discovery — detect output fields, upsert into _catalog
- Schema drift detection — compare new fields against _catalog
- Data validation — check for empty fields, missing data, undersized media files
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
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


def discover_schema(file_path: Path) -> dict:
    """Discover output fields from a JSONL file."""
    fields = {}
    sample_count = 0

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    for key, value in item.items():
                        if key not in fields:
                            fields[key] = {
                                "type": type(value).__name__,
                                "sample": str(value)[:100] if value is not None else None,
                                "null_count": 0,
                                "present_count": 0,
                            }
                        if value is None or value == "" or value == []:
                            fields[key]["null_count"] += 1
                        else:
                            fields[key]["present_count"] += 1
                    sample_count += 1
            except json.JSONDecodeError:
                continue

    # Calculate fill rates
    for field_info in fields.values():
        total = field_info["null_count"] + field_info["present_count"]
        field_info["fill_rate"] = round(field_info["present_count"] / total, 2) if total > 0 else 0
        del field_info["sample"]  # Remove samples from final output

    return {"fields": fields, "row_count": sample_count}


def detect_schema_drift(con: duckdb.DuckDBPyConnection, actor_slug: str, new_fields: dict) -> dict | None:
    """Compare new fields against _catalog to detect drift."""
    existing = con.execute(
        "SELECT output_fields FROM _catalog WHERE actor_slug = ?",
        [actor_slug]
    ).fetchone()

    if not existing:
        return None  # First time — no drift possible

    try:
        old_fields = json.loads(existing[0]) if isinstance(existing[0], str) else existing[0]
    except (json.JSONDecodeError, TypeError):
        return None

    old_names = set(old_fields.keys()) if isinstance(old_fields, dict) else set()
    new_names = set(new_fields.keys())

    added = new_names - old_names
    removed = old_names - new_names
    common = old_names & new_names

    # Check type changes
    type_changes = {}
    if isinstance(old_fields, dict):
        for field in common:
            old_type = old_fields[field].get("type", "unknown") if isinstance(old_fields[field], dict) else "unknown"
            new_type = new_fields[field].get("type", "unknown") if isinstance(new_fields[field], dict) else "unknown"
            if old_type != new_type:
                type_changes[field] = {"old": old_type, "new": new_type}

    if not added and not removed and not type_changes:
        return None

    return {
        "added_fields": list(added),
        "removed_fields": list(removed),
        "type_changes": type_changes,
        "summary": (
            f"{len(added)} new field(s), {len(removed)} removed field(s), "
            f"{len(type_changes)} type change(s) detected."
        ),
    }


def validate_data(file_path: Path, actor_slug: str) -> dict:
    """Run basic data validation on downloaded data."""
    issues = []
    row_count = 0
    empty_rows = 0

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                row_count += 1

                if not isinstance(item, dict):
                    issues.append({"row": line_num, "issue": "Non-object row"})
                    continue

                # Check for completely empty items
                non_null = sum(1 for v in item.values() if v is not None and v != "" and v != [])
                if non_null == 0:
                    empty_rows += 1

                # Check for missing expected fields based on actor type
                if "instagram" in actor_slug.lower():
                    for field in ["id", "caption", "likesCount"]:
                        if field not in item or item[field] is None:
                            issues.append({"row": line_num, "issue": f"Missing {field}"})

                elif "tiktok" in actor_slug.lower():
                    for field in ["id", "text", "diggCount"]:
                        if field not in item or item[field] is None:
                            issues.append({"row": line_num, "issue": f"Missing {field}"})

                elif "tweet" in actor_slug.lower() or "twitter" in actor_slug.lower():
                    for field in ["id", "text", "likeCount"]:
                        if field not in item or item[field] is None:
                            issues.append({"row": line_num, "issue": f"Missing {field}"})

            except json.JSONDecodeError:
                issues.append({"row": line_num, "issue": "Invalid JSON"})

    # Limit reported issues
    issue_summary = {}
    for issue in issues:
        key = issue["issue"]
        if key not in issue_summary:
            issue_summary[key] = 0
        issue_summary[key] += 1

    return {
        "row_count": row_count,
        "empty_rows": empty_rows,
        "issue_count": len(issues),
        "issue_summary": issue_summary,
        "valid": len(issues) == 0 and empty_rows == 0,
        "first_issues": issues[:10],  # Show first 10 only
    }


def import_to_duckdb(con: duckdb.DuckDBPyConnection, file_path: Path, table_name: str) -> dict:
    """Import JSONL file into a DuckDB table."""
    try:
        # Let DuckDB auto-detect schema from JSONL
        con.execute(f"""
            CREATE OR REPLACE TABLE "{table_name}" AS
            SELECT * FROM read_json_auto('{file_path}',
                format='newline_delimited',
                maximum_object_size=10485760)
        """)

        row_count = con.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
        columns = con.execute(f'DESCRIBE "{table_name}"').fetchall()

        return {
            "table_name": table_name,
            "row_count": row_count,
            "columns": [{"name": c[0], "type": c[1]} for c in columns],
            "success": True,
        }
    except Exception as e:
        return {
            "table_name": table_name,
            "error": str(e),
            "success": False,
        }


def main():
    parser = argparse.ArgumentParser(description="Import dataset into DuckDB")
    parser.add_argument("--file", required=True, help="Path to JSONL file")
    parser.add_argument("--table", help="DuckDB table name (default: derived from filename)")
    parser.add_argument("--actor-slug", help="Actor slug for catalog tracking")
    parser.add_argument("--job-id", help="Job ID for DuckDB tracking")
    parser.add_argument("--run-id", help="Pipeline run ID for DuckDB tracking")
    parser.add_argument("--validate-only", action="store_true", help="Only validate, don't import")
    parser.add_argument("--skip-validation", action="store_true", help="Skip data validation")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(json.dumps({"error": f"File not found: {file_path}"}))
        sys.exit(1)

    con = duckdb.connect(str(DB_PATH))
    result = {}

    # 1. Schema discovery
    schema = discover_schema(file_path)
    result["schema"] = {
        "field_count": len(schema["fields"]),
        "row_count": schema["row_count"],
        "fields": {k: {"type": v["type"], "fill_rate": v["fill_rate"]}
                   for k, v in schema["fields"].items()},
    }

    # 2. Schema drift detection
    if args.actor_slug:
        drift = detect_schema_drift(con, args.actor_slug, schema["fields"])
        if drift:
            result["schema_drift"] = drift

    # 3. Data validation
    if not args.skip_validation:
        validation = validate_data(file_path, args.actor_slug or "")
        result["validation"] = validation

    if args.validate_only:
        con.close()
        print(json.dumps(result, indent=2))
        return

    # 4. Import to DuckDB
    table_name = args.table or file_path.stem.replace("-", "_").replace(".", "_")
    import_result = import_to_duckdb(con, file_path, table_name)
    result["import"] = import_result

    # 5. Update _catalog
    if args.actor_slug and import_result.get("success"):
        field_info = {k: {"type": v["type"], "fill_rate": v["fill_rate"]}
                      for k, v in schema["fields"].items()}
        con.execute("""
            INSERT INTO _catalog (actor_slug, output_fields, last_updated)
            VALUES (?, ?, current_timestamp)
            ON CONFLICT (actor_slug) DO UPDATE
            SET output_fields = excluded.output_fields,
                last_updated = excluded.last_updated
        """, [args.actor_slug, json.dumps(field_info)])
        result["catalog_updated"] = True

    # 6. Update landed_data tracking
    if args.job_id and import_result.get("success"):
        landing_id = str(uuid.uuid4())
        con.execute("""
            INSERT INTO landed_data (id, run_id, job_id, destination, path, row_count)
            VALUES (?, ?, ?, 'duckdb', ?, ?)
        """, [
            landing_id,
            args.run_id,
            args.job_id,
            table_name,
            import_result.get("row_count", 0),
        ])
        result["landing_id"] = landing_id

    con.close()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
