# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.1.0",
#     "httpx>=0.27.0",
# ]
# ///
"""
INIT phase script — runs on SessionStart hook.

Responsibilities:
1. Initialize DuckDB schema if needed (7 tables including _user_config, _actor_registry)
2. Check _actor_registry staleness, refresh if >24h stale (with pricing data)
3. Query DuckDB for incomplete runs from previous sessions, poll Apify for status
4. Read/create user profile in _user_config table
5. One-time migration from legacy JSON files (config.json, actor_registry.json)
6. Output summary for Claude to present to user
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import httpx

from _log import log

# Paths
PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).parent.parent))
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
LEGACY_CONFIG_FILE = DATA_DIR / "config.json"
LEGACY_REGISTRY_FILE = DATA_DIR / "actor_registry.json"

APIFY_API_BASE = "https://api.apify.com/v2"
REGISTRY_MAX_AGE_HOURS = 24

# Actors known to require residential proxies
RESIDENTIAL_PROXY_ACTORS = {
    "apify/instagram-scraper",
    "clockworks/tiktok-scraper",
    "apify/facebook-posts-scraper",
    "junglee/amazon-crawler",
    "piotrv1001/walmart-listings-scraper",
}



def get_apify_token() -> str | None:
    """Get Apify API token from environment or .env file."""
    # Check environment first
    token = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
    if token:
        return token

    # Check project .env file
    env_file = PROJECT_DIR / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("\"'")
                if key in ("APIFY_TOKEN", "APIFY_API_TOKEN") and value:
                    return value
        except Exception:
            pass

    return None


def ensure_dirs():
    """Create required directories."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)



def init_duckdb_schema(con: duckdb.DuckDBPyConnection):
    """Initialize DuckDB tables if they don't exist."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id VARCHAR PRIMARY KEY,
            session_id VARCHAR,
            user_request TEXT,
            task_list_id VARCHAR,
            status VARCHAR DEFAULT 'queued',
            config JSON,
            estimated_cost DOUBLE,
            created_at TIMESTAMP DEFAULT current_timestamp,
            completed_at TIMESTAMP,
            summary TEXT
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS apify_jobs (
            job_id VARCHAR PRIMARY KEY,
            run_id VARCHAR REFERENCES pipeline_runs(run_id),
            apify_run_id VARCHAR,
            actor_id VARCHAR,
            task_id VARCHAR,
            status VARCHAR DEFAULT 'pending',
            dataset_id VARCHAR,
            dispatched_at TIMESTAMP,
            completed_at TIMESTAMP,
            error TEXT
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS landed_data (
            id VARCHAR PRIMARY KEY,
            run_id VARCHAR REFERENCES pipeline_runs(run_id),
            job_id VARCHAR REFERENCES apify_jobs(job_id),
            destination VARCHAR,
            path VARCHAR,
            row_count INTEGER,
            landed_at TIMESTAMP DEFAULT current_timestamp
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS _catalog (
            actor_slug VARCHAR PRIMARY KEY,
            output_fields JSON,
            last_updated TIMESTAMP DEFAULT current_timestamp
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS _diagnostics (
            job_id VARCHAR REFERENCES apify_jobs(job_id),
            estimated_cost DOUBLE,
            actual_cost DOUBLE,
            estimated_time DOUBLE,
            actual_time DOUBLE,
            actor_ram_utilization DOUBLE,
            items_requested INTEGER,
            items_returned INTEGER,
            recorded_at TIMESTAMP DEFAULT current_timestamp
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS _user_config (
            key VARCHAR PRIMARY KEY,
            value VARCHAR,
            updated_at TIMESTAMP DEFAULT current_timestamp
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS _actor_registry (
            actor_id VARCHAR PRIMARY KEY,
            name VARCHAR,
            title VARCHAR,
            description TEXT,
            total_runs INTEGER,
            last_run_at TIMESTAMP,
            input_schema JSON,
            cost_per_1000_usd DOUBLE,
            cost_sample_runs INTEGER,
            proxy_type VARCHAR,
            pricing_model VARCHAR,
            refreshed_at TIMESTAMP DEFAULT current_timestamp
        )
    """)


def load_config(con: duckdb.DuckDBPyConnection) -> dict:
    """Load user config from _user_config table."""
    rows = con.execute("SELECT key, value FROM _user_config").fetchall()
    return {key: value for key, value in rows}


def save_config(con: duckdb.DuckDBPyConnection, config: dict):
    """Save user config to _user_config table via UPSERT."""
    for key, value in config.items():
        con.execute("""
            INSERT INTO _user_config (key, value, updated_at)
            VALUES (?, ?, current_timestamp)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = current_timestamp
        """, [key, str(value)])


def check_registry_freshness(con: duckdb.DuckDBPyConnection) -> bool:
    """Check if actor registry needs refresh. Returns True if stale."""
    result = con.execute("SELECT MAX(refreshed_at) FROM _actor_registry").fetchone()
    if not result or result[0] is None:
        return True
    last_refreshed = result[0]
    if isinstance(last_refreshed, str):
        last_refreshed = datetime.fromisoformat(last_refreshed)
    # Make naive datetimes UTC-aware for comparison
    if last_refreshed.tzinfo is None:
        last_refreshed = last_refreshed.replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - last_refreshed).total_seconds() / 3600
    return age_hours > REGISTRY_MAX_AGE_HOURS


# Core actors we track — these are the ones referenced in our skills
CORE_ACTORS = [
    "apify/instagram-scraper",
    "clockworks/tiktok-scraper",
    "apidojo/tweet-scraper",
    "apify/facebook-posts-scraper",
    "junglee/amazon-crawler",
    "piotrv1001/walmart-listings-scraper",
    "autofacts/shopify",
    "apify/e-commerce-scraping-tool",
    "compass/crawler-google-places",
    "compass/Google-Maps-Reviews-Scraper",
]


def _calculate_cost_per_1000(runs: list[dict]) -> tuple[float | None, int]:
    """Calculate cost per 1000 results from recent successful runs.

    Returns (cost_per_1000_usd, sample_count). cost is None if no usable data.
    """
    costs = []
    for run in runs:
        usage_usd = run.get("usageTotalUsd")
        items = run.get("stats", {}).get("itemsCount", 0)
        if usage_usd and items and items > 0:
            costs.append((usage_usd, items))

    if not costs:
        return None, 0

    total_cost = sum(c[0] for c in costs)
    total_items = sum(c[1] for c in costs)
    if total_items == 0:
        return None, 0

    cost_per_1000 = (total_cost / total_items) * 1000
    return round(cost_per_1000, 4), len(costs)


def refresh_registry(con: duckdb.DuckDBPyConnection, token: str) -> int:
    """Refresh actor registry from Apify API into _actor_registry table.

    Returns count of actors successfully refreshed.
    """
    client = httpx.Client(
        base_url=APIFY_API_BASE,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )

    refreshed = 0
    now = datetime.now(timezone.utc).isoformat()

    for actor_id in CORE_ACTORS:
        # Slash notation → tilde for API URL paths
        api_actor_id = actor_id.replace("/", "~")
        try:
            resp = client.get(f"/acts/{api_actor_id}")
            if resp.status_code != 200:
                continue

            data = resp.json().get("data", {})

            # Extract input schema
            input_schema = {}
            try:
                schema_resp = client.get(f"/acts/{api_actor_id}/input-schema")
                if schema_resp.status_code == 200:
                    input_schema = schema_resp.json().get("data", {})
            except Exception:
                pass

            # Fetch recent runs for pricing data
            cost_per_1000_usd = None
            cost_sample_runs = 0
            try:
                runs_resp = client.get(f"/acts/{api_actor_id}/runs", params={"limit": 5, "desc": True})
                if runs_resp.status_code == 200:
                    runs = runs_resp.json().get("data", {}).get("items", [])
                    cost_per_1000_usd, cost_sample_runs = _calculate_cost_per_1000(runs)
            except Exception:
                pass

            # Detect proxy type
            proxy_type = "residential" if actor_id in RESIDENTIAL_PROXY_ACTORS else "datacenter"

            # Detect pricing model
            pricing = data.get("pricing", {})
            pricing_model = pricing.get("pricingModel", "PAY_PER_RESULT")

            # Input schema summary as JSON
            schema_summary = {
                "required": input_schema.get("required", []),
                "properties": list(input_schema.get("properties", {}).keys())[:20],
            }

            con.execute("""
                INSERT INTO _actor_registry (
                    actor_id, name, title, description, total_runs, last_run_at,
                    input_schema, cost_per_1000_usd, cost_sample_runs,
                    proxy_type, pricing_model, refreshed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (actor_id) DO UPDATE SET
                    name = EXCLUDED.name, title = EXCLUDED.title,
                    description = EXCLUDED.description, total_runs = EXCLUDED.total_runs,
                    last_run_at = EXCLUDED.last_run_at, input_schema = EXCLUDED.input_schema,
                    cost_per_1000_usd = EXCLUDED.cost_per_1000_usd,
                    cost_sample_runs = EXCLUDED.cost_sample_runs,
                    proxy_type = EXCLUDED.proxy_type, pricing_model = EXCLUDED.pricing_model,
                    refreshed_at = EXCLUDED.refreshed_at
            """, [
                actor_id,
                data.get("name", ""),
                data.get("title", ""),
                (data.get("description", "") or "")[:200],
                data.get("stats", {}).get("totalRuns", 0),
                data.get("stats", {}).get("lastRunStartedAt"),
                json.dumps(schema_summary),
                cost_per_1000_usd,
                cost_sample_runs,
                proxy_type,
                pricing_model,
                now,
            ])
            refreshed += 1

        except Exception as e:
            log("session_start", f"registry refresh failed for {actor_id}: {e}")

    client.close()
    return refreshed


def migrate_legacy_files(con: duckdb.DuckDBPyConnection):
    """One-time migration: import data from legacy JSON files into DuckDB, then delete them."""
    migrated = []

    # Migrate config.json → _user_config
    if LEGACY_CONFIG_FILE.exists():
        try:
            config = json.loads(LEGACY_CONFIG_FILE.read_text(encoding="utf-8"))
            for key, value in config.items():
                con.execute("""
                    INSERT INTO _user_config (key, value, updated_at)
                    VALUES (?, ?, current_timestamp)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = current_timestamp
                """, [key, str(value)])
            LEGACY_CONFIG_FILE.unlink()
            migrated.append(f"config.json ({len(config)} keys)")
        except Exception as e:
            log("session_start", f"config migration failed: {e}")

    # Migrate actor_registry.json → _actor_registry
    if LEGACY_REGISTRY_FILE.exists():
        try:
            registry = json.loads(LEGACY_REGISTRY_FILE.read_text(encoding="utf-8"))
            actors = registry.get("actors", {})
            for actor_id, info in actors.items():
                if info.get("error"):
                    continue  # Skip entries that were errors
                schema_summary = info.get("input_schema_summary", {})
                con.execute("""
                    INSERT INTO _actor_registry (
                        actor_id, name, title, description, total_runs, last_run_at,
                        input_schema, refreshed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (actor_id) DO NOTHING
                """, [
                    actor_id,
                    info.get("name", ""),
                    info.get("title", ""),
                    info.get("description", ""),
                    info.get("stats", {}).get("totalRuns", 0),
                    info.get("stats", {}).get("lastRunAt"),
                    json.dumps(schema_summary),
                    info.get("last_updated", datetime.now(timezone.utc).isoformat()),
                ])
            LEGACY_REGISTRY_FILE.unlink()
            migrated.append(f"actor_registry.json ({len(actors)} actors)")
        except Exception as e:
            log("session_start", f"registry migration failed: {e}")

    return migrated


def check_incomplete_runs(con: duckdb.DuckDBPyConnection, token: str | None) -> list[dict]:
    """Check for incomplete runs from previous sessions and poll Apify for status."""
    incomplete = con.execute("""
        SELECT j.job_id, j.apify_run_id, j.actor_id, j.status, j.dataset_id,
               p.user_request, p.run_id as pipeline_run_id
        FROM apify_jobs j
        JOIN pipeline_runs p ON j.run_id = p.run_id
        WHERE j.status IN ('pending', 'dispatched', 'running')
        ORDER BY j.dispatched_at
    """).fetchall()

    if not incomplete:
        return []

    results = []
    client = None
    if token:
        client = httpx.Client(
            base_url=APIFY_API_BASE,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )

    for job_id, apify_run_id, actor_id, status, dataset_id, user_request, pipeline_run_id in incomplete:
        job_info = {
            "job_id": job_id,
            "apify_run_id": apify_run_id,
            "actor_id": actor_id,
            "previous_status": status,
            "current_status": status,
            "user_request": user_request,
            "dataset_id": dataset_id,
        }

        # Poll Apify for current status if we have a token and run ID
        if client and apify_run_id:
            try:
                resp = client.get(f"/actor-runs/{apify_run_id}")
                if resp.status_code == 200:
                    run_data = resp.json().get("data", {})
                    apify_status = run_data.get("status", "UNKNOWN")

                    # Map Apify status to our status
                    status_map = {
                        "READY": "pending",
                        "RUNNING": "running",
                        "SUCCEEDED": "succeeded",
                        "FAILED": "failed",
                        "ABORTING": "failed",
                        "ABORTED": "failed",
                        "TIMED-OUT": "failed",
                    }
                    new_status = status_map.get(apify_status, status)
                    job_info["current_status"] = new_status
                    job_info["apify_status"] = apify_status

                    # Get dataset ID if job succeeded
                    if new_status == "succeeded":
                        job_info["dataset_id"] = run_data.get("defaultDatasetId")

                    # Update DuckDB
                    if new_status != status:
                        con.execute("""
                            UPDATE apify_jobs
                            SET status = ?, dataset_id = COALESCE(?, dataset_id),
                                completed_at = CASE WHEN ? IN ('succeeded', 'failed')
                                    THEN current_timestamp ELSE completed_at END
                            WHERE job_id = ?
                        """, [new_status, job_info.get("dataset_id"), new_status, job_id])

                        # Update pipeline run if all jobs complete
                        all_done = con.execute("""
                            SELECT COUNT(*) = 0 FROM apify_jobs
                            WHERE run_id = ? AND status IN ('pending', 'dispatched', 'running')
                        """, [pipeline_run_id]).fetchone()[0]

                        if all_done:
                            any_failed = con.execute("""
                                SELECT COUNT(*) > 0 FROM apify_jobs
                                WHERE run_id = ? AND status = 'failed'
                            """, [pipeline_run_id]).fetchone()[0]
                            pipeline_status = "failed" if any_failed else "complete"
                            con.execute("""
                                UPDATE pipeline_runs
                                SET status = ?, completed_at = current_timestamp
                                WHERE run_id = ?
                            """, [pipeline_status, pipeline_run_id])

            except Exception as e:
                job_info["poll_error"] = str(e)

        results.append(job_info)

    if client:
        client.close()

    return results


def main():
    parser = argparse.ArgumentParser(description="Apify plugin session initialization")
    parser.add_argument("--check-registry", metavar="QUERY",
                        help="Search local registry for an actor matching QUERY")
    parser.add_argument("--force-refresh", action="store_true",
                        help="Force registry refresh regardless of age")
    args = parser.parse_args()

    log("session_start", f"starting — PROJECT_DIR={PROJECT_DIR}, PLUGIN_ROOT={PLUGIN_ROOT}")
    ensure_dirs()
    token = get_apify_token()
    log("session_start", f"token={'found' if token else 'MISSING'}")

    # Handle registry search
    if args.check_registry:
        con = duckdb.connect(str(DB_PATH))
        init_duckdb_schema(con)
        query = args.check_registry.lower()
        rows = con.execute("""
            SELECT actor_id, name, title, description, total_runs, last_run_at,
                   input_schema, cost_per_1000_usd, cost_sample_runs, proxy_type,
                   pricing_model, refreshed_at
            FROM _actor_registry
            WHERE LOWER(actor_id) LIKE ? OR LOWER(name) LIKE ?
               OR LOWER(title) LIKE ? OR LOWER(COALESCE(description, '')) LIKE ?
        """, [f"%{query}%"] * 4).fetchall()
        matches = []
        for row in rows:
            matches.append({
                "actor_id": row[0], "name": row[1], "title": row[2],
                "description": row[3], "total_runs": row[4],
                "last_run_at": str(row[5]) if row[5] else None,
                "input_schema": json.loads(row[6]) if row[6] else {},
                "cost_per_1000_usd": row[7], "cost_sample_runs": row[8],
                "proxy_type": row[9], "pricing_model": row[10],
                "refreshed_at": str(row[11]) if row[11] else None,
            })
        con.close()
        print(json.dumps({"matches": matches, "count": len(matches)}, indent=2))
        return

    # Full session initialization
    output = {
        "status": "initialized",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "warnings": [],
        "actions_taken": [],
    }

    # 0. Check for API token — block setup if missing
    if not token:
        output["status"] = "setup_required"
        output["setup_required"] = {
            "issue": "no_api_token",
            "message": "Apify API token not found. The plugin needs this to dispatch scraping jobs, download data, and check costs.",
            "checked_locations": [
                "APIFY_TOKEN environment variable",
                "APIFY_API_TOKEN environment variable",
                f"{PROJECT_DIR / '.env'} file",
            ],
            "setup_instructions": {
                "step_1": "Authenticate the Apify MCP server — the OAuth prompt should appear automatically. This gives Claude access to the Apify actor store.",
                "step_2": "Sign up at https://apify.com/sign-up if needed (free tier available)",
                "step_3": "Go to https://console.apify.com/account/integrations and copy your Personal API token",
                "step_4_option_a": {
                    "method": "Project .env file (recommended)",
                    "action": f"Create a .env file at {PROJECT_DIR / '.env'} with the line: APIFY_TOKEN=apify_api_XXXXX",
                    "note": "Make sure .env is in your .gitignore",
                },
                "step_4_option_b": {
                    "method": "Shell environment variable",
                    "action": "Add to your shell profile (~/.bashrc, ~/.zshrc, etc.): export APIFY_TOKEN=apify_api_XXXXX",
                },
                "step_5": "Restart this Claude Code session after setting the token.",
            },
            "note": "The Apify MCP server uses OAuth (browser sign-in) for actor discovery. The REST API token is needed separately for plugin scripts (dispatching jobs, downloading data, cost estimation).",
        }
        output["_instruction"] = (
            "IMPORTANT: The Apify API token is not configured. "
            "Tell the user they need to set up their API token before the plugin can dispatch jobs. "
            "Walk them through the setup_instructions above. Do NOT proceed with any scraping until the token is set."
        )
        # Still initialize DuckDB even without token
        con = duckdb.connect(str(DB_PATH))
        init_duckdb_schema(con)
        migrated = migrate_legacy_files(con)
        con.close()
        output["actions_taken"].append("DuckDB schema initialized (token still needed for full functionality)")
        if migrated:
            output["actions_taken"].append(f"Migrated legacy files: {', '.join(migrated)}")
        print(json.dumps(output, indent=2, default=str))
        return

    # 1. Initialize DuckDB
    con = duckdb.connect(str(DB_PATH))
    init_duckdb_schema(con)
    output["actions_taken"].append("DuckDB schema initialized")

    # 1b. One-time migration from legacy JSON files
    migrated = migrate_legacy_files(con)
    if migrated:
        output["actions_taken"].append(f"Migrated legacy files: {', '.join(migrated)}")

    # 2. Check and refresh registry
    if args.force_refresh or check_registry_freshness(con):
        try:
            actor_count = refresh_registry(con, token)
            output["actions_taken"].append(f"Actor registry refreshed ({actor_count} actors, with pricing)")
        except Exception as e:
            output["warnings"].append(f"Registry refresh failed: {e}")
    else:
        output["actions_taken"].append("Actor registry is fresh (< 24h old)")

    # 3. Check for incomplete runs
    incomplete = check_incomplete_runs(con, token)
    if incomplete:
        output["incomplete_runs"] = incomplete
        succeeded = [r for r in incomplete if r["current_status"] == "succeeded"]
        still_running = [r for r in incomplete if r["current_status"] == "running"]
        failed = [r for r in incomplete if r["current_status"] == "failed"]

        if succeeded:
            output["warnings"].append(
                f"{len(succeeded)} job(s) completed since last session. "
                "Data ready to download — ask where to land it."
            )
            # Check for media jobs that may have KV storage costs
            for job in succeeded:
                if any(kw in (job.get("actor_id") or "").lower()
                       for kw in ["video", "media", "tiktok", "instagram"]):
                    output["warnings"].append(
                        f"Job {job['job_id']} ({job['actor_id']}) may have media in Apify KV storage. "
                        "KV storage is billed per GB-hour — download and delete to save costs."
                    )
        if still_running:
            output["warnings"].append(f"{len(still_running)} job(s) still running on Apify.")
        if failed:
            output["warnings"].append(f"{len(failed)} job(s) failed. Review errors and decide on retry.")

    # 4. Load/check user profile
    config = load_config(con)
    if config:
        output["user_profile"] = {
            "role": config.get("role", "unknown"),
            "skill_level": config.get("skill_level", "unknown"),
            "default_destination": config.get("default_destination", "not set"),
            "media_preference": config.get("media_preference", "not set"),
        }
        output["actions_taken"].append("User profile loaded")
    else:
        output["first_run"] = True
        output["actions_taken"].append("First run detected — user profile needed")
        output["setup_questions"] = [
            {
                "question": "What's your role? This helps me adapt explanations.",
                "options": ["Developer/Technical", "Data Analyst", "Marketing/Business", "Researcher", "Other"],
            },
            {
                "question": "Where should extracted data go by default?",
                "options": ["DuckDB (local database)", "JSON files (local)", "Decide each time"],
            },
        ]
        output["_instruction"] = (
            "IMPORTANT: This is the user's first session with the Apify plugin. "
            "Before doing anything else, greet the user and ask them the setup_questions above "
            "using AskUserQuestion. Save their answers by running: "
            f'uv run "{PLUGIN_ROOT}/scripts/save_config.py" --set "role=ANSWER" --set "default_destination=ANSWER" --set "onboarding_complete=true". '
            "This only happens once."
        )

    # 5. Maintenance hint
    output["hint"] = "Run /maintenance periodically to check storage costs, consumption, and spending trends."

    con.close()
    log("session_start", f"done — status={output['status']}, actions={output['actions_taken']}")
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
