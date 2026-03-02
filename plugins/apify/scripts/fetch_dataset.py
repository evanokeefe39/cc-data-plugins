# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx>=0.27.0",
#     "duckdb>=1.1.0",
# ]
# ///
"""
Stream Apify dataset to local files via REST API.

Data NEVER passes through the LLM context window. This script streams datasets
directly to JSONL files on disk. Claude sees only summary metadata.
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import httpx

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd()))
DATA_DIR = PROJECT_DIR / ".apify_plugin" / "data"
DB_PATH = DATA_DIR / "datasets.duckdb"

APIFY_API_BASE = "https://api.apify.com/v2"


def get_apify_token() -> str:
    from _token import get_apify_token as _get
    token = _get()
    if not token:
        print(json.dumps({"error": "No APIFY_TOKEN set. Check .env or environment variables."}))
        sys.exit(1)
    return token


def stream_dataset(dataset_id: str, output_path: Path, token: str, format: str = "jsonl") -> dict:
    """Stream dataset from Apify to local file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine API format parameter
    api_format = "json" if format == "jsonl" else format

    url = f"{APIFY_API_BASE}/datasets/{dataset_id}/items"
    params = {
        "format": api_format,
        "clean": "true",  # Remove empty items
    }
    headers = {"Authorization": f"Bearer {token}"}

    row_count = 0
    bytes_written = 0

    with httpx.Client(timeout=300) as client:
        # Stream response to file
        with client.stream("GET", url, params=params, headers=headers) as response:
            if response.status_code != 200:
                return {
                    "error": f"HTTP {response.status_code}: {response.text[:500] if hasattr(response, 'text') else 'Unknown error'}",
                    "dataset_id": dataset_id,
                }

            if format == "jsonl":
                # Parse JSON array and write as JSONL
                content = b""
                for chunk in response.iter_bytes():
                    content += chunk

                try:
                    items = json.loads(content)
                    if isinstance(items, list):
                        with open(output_path, "w", encoding="utf-8") as f:
                            for item in items:
                                line = json.dumps(item, ensure_ascii=False)
                                f.write(line + "\n")
                                row_count += 1
                                bytes_written += len(line) + 1
                    else:
                        # Single item
                        with open(output_path, "w", encoding="utf-8") as f:
                            line = json.dumps(items, ensure_ascii=False)
                            f.write(line + "\n")
                            row_count = 1
                            bytes_written = len(line) + 1
                except json.JSONDecodeError as e:
                    return {"error": f"Failed to parse dataset JSON: {e}", "dataset_id": dataset_id}
            else:
                # Write raw (CSV, etc.)
                with open(output_path, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)
                        bytes_written += len(chunk)
                # Count lines for CSV
                if format == "csv":
                    with open(output_path, "r", encoding="utf-8") as f:
                        row_count = sum(1 for _ in f) - 1  # subtract header

    return {
        "dataset_id": dataset_id,
        "output_path": str(output_path),
        "format": format,
        "row_count": row_count,
        "bytes_written": bytes_written,
        "size_mb": round(bytes_written / (1024 * 1024), 2),
    }


def sanitize_text(file_path: Path) -> dict:
    """Clean text data: null bytes, encoding issues, control characters."""
    import re

    cleaned_count = 0
    lines = []

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            original = line
            # Remove null bytes
            line = line.replace("\x00", "")
            # Remove other control characters (keep newlines, tabs)
            line = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", line)
            if line != original:
                cleaned_count += 1
            lines.append(line)

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    return {"cleaned_lines": cleaned_count, "total_lines": len(lines)}


def main():
    parser = argparse.ArgumentParser(description="Fetch Apify dataset to local files")
    parser.add_argument("--dataset-id", required=True, help="Apify dataset ID")
    parser.add_argument("--job-id", help="Job ID for DuckDB tracking")
    parser.add_argument("--run-id", help="Pipeline run ID for DuckDB tracking")
    parser.add_argument("--output", help="Output file path (default: data/<dataset_id>.jsonl)")
    parser.add_argument("--format", choices=["jsonl", "csv"], default="jsonl", help="Output format")
    parser.add_argument("--sanitize", action="store_true", help="Clean text data after download")
    args = parser.parse_args()

    token = get_apify_token()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        ext = "jsonl" if args.format == "jsonl" else "csv"
        output_path = DATA_DIR / f"{args.dataset_id}.{ext}"

    # Stream dataset
    result = stream_dataset(args.dataset_id, output_path, token, args.format)

    if "error" in result:
        print(json.dumps(result, indent=2))
        sys.exit(1)

    # Sanitize if requested
    if args.sanitize and args.format == "jsonl":
        sanitize_result = sanitize_text(output_path)
        result["sanitization"] = sanitize_result

    # Record in DuckDB
    if args.job_id or args.run_id:
        try:
            con = duckdb.connect(str(DB_PATH))
            landing_id = str(uuid.uuid4())
            con.execute("""
                INSERT INTO landed_data (id, run_id, job_id, destination, path, row_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                landing_id,
                args.run_id,
                args.job_id,
                f"local_{args.format}",
                str(output_path),
                result["row_count"],
            ])
            con.close()
            result["landing_id"] = landing_id
            result["tracked_in_duckdb"] = True
        except Exception as e:
            result["tracking_error"] = str(e)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
