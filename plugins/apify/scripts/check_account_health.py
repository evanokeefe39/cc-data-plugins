# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx>=0.27.0",
#     "duckdb>=1.1.0",
# ]
# ///
"""
Account health check — storage costs, spending trends, stale datasets.

Checks:
1. Account balance (USD) and burn rate
2. Storage usage (datasets, KV stores)
3. Stale datasets still on Apify
4. Cost accuracy (estimated vs actual from _diagnostics)
5. Recent spending (USD) by actor
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import duckdb
import httpx

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

APIFY_API_BASE = "https://api.apify.com/v2"


def get_apify_token() -> str:
    from _token import get_apify_token as _get
    token = _get()
    if not token:
        print(json.dumps({"error": "No APIFY_TOKEN set. Check .env or environment variables."}))
        sys.exit(1)
    return token


def check_account_info(client: httpx.Client) -> dict:
    """Get account info including USD balance."""
    try:
        resp = client.get("/v2/users/me")
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            plan = data.get("plan", {})
            return {
                "username": data.get("username"),
                "plan": plan.get("id", "unknown"),
                "balance_remaining_usd": plan.get("usageCreditsRemaining"),
                "monthly_limit_usd": plan.get("monthlyUsageCreditsLimit"),
                "used_this_period_usd": plan.get("usageCreditsUsedThisPeriod"),
            }
    except Exception as e:
        return {"error": str(e)}
    return {"error": "Could not fetch account info"}


def check_storage(client: httpx.Client) -> dict:
    """Check storage usage — datasets, KV stores, request queues."""
    storage = {"datasets": [], "kv_stores": [], "total_size_bytes": 0}

    # Check datasets
    try:
        resp = client.get("/v2/datasets", params={"limit": 100, "desc": True})
        if resp.status_code == 200:
            items = resp.json().get("data", {}).get("items", [])
            for ds in items:
                created = ds.get("createdAt", "")
                age_days = 0
                if created:
                    try:
                        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        age_days = (datetime.now(timezone.utc) - created_dt).days
                    except ValueError:
                        pass

                ds_info = {
                    "id": ds.get("id"),
                    "name": ds.get("name", "unnamed"),
                    "item_count": ds.get("itemCount", 0),
                    "size_bytes": ds.get("stats", {}).get("s3StorageBytes", 0),
                    "created_at": created,
                    "age_days": age_days,
                    "stale": age_days > 7,
                }
                storage["datasets"].append(ds_info)
                storage["total_size_bytes"] += ds_info["size_bytes"]
    except Exception as e:
        storage["dataset_error"] = str(e)

    # Check KV stores
    try:
        resp = client.get("/v2/key-value-stores", params={"limit": 100, "desc": True})
        if resp.status_code == 200:
            items = resp.json().get("data", {}).get("items", [])
            for kv in items:
                created = kv.get("createdAt", "")
                age_days = 0
                if created:
                    try:
                        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        age_days = (datetime.now(timezone.utc) - created_dt).days
                    except ValueError:
                        pass

                kv_info = {
                    "id": kv.get("id"),
                    "name": kv.get("name", "unnamed"),
                    "size_bytes": kv.get("stats", {}).get("s3StorageBytes", 0),
                    "created_at": created,
                    "age_days": age_days,
                    "gb_hours_per_day": round(kv.get("stats", {}).get("s3StorageBytes", 0) / (1024**3) * 24, 4),
                }
                storage["kv_stores"].append(kv_info)
                storage["total_size_bytes"] += kv_info["size_bytes"]
    except Exception as e:
        storage["kv_error"] = str(e)

    storage["total_size_mb"] = round(storage["total_size_bytes"] / (1024 * 1024), 2)
    storage["stale_datasets"] = [d for d in storage["datasets"] if d.get("stale")]
    storage["stale_count"] = len(storage["stale_datasets"])

    return storage


def _aggregate_runs(runs: list[dict], cutoff: datetime) -> dict:
    """Aggregate runs newer than cutoff by actor."""
    by_actor = {}
    total_usd = 0.0
    total_runs = 0

    for run in runs:
        started = run.get("startedAt", "")
        if not started:
            continue
        try:
            started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            if started_dt < cutoff:
                continue
        except ValueError:
            continue

        actor_id = run.get("actId", "unknown")
        usage_usd = run.get("usageTotalUsd", 0) or 0

        if actor_id not in by_actor:
            by_actor[actor_id] = {"runs": 0, "total_usd": 0, "items": 0}
        by_actor[actor_id]["runs"] += 1
        by_actor[actor_id]["total_usd"] += usage_usd
        by_actor[actor_id]["items"] += run.get("stats", {}).get("itemsCount", 0)
        total_usd += usage_usd
        total_runs += 1

    actors = []
    for actor_id, info in sorted(by_actor.items(), key=lambda x: x[1]["total_usd"], reverse=True):
        actors.append({
            "actor_id": actor_id,
            "runs": info["runs"],
            "total_usd": round(info["total_usd"], 4),
            "total_items": info["items"],
        })

    return {"by_actor": actors, "total_usd": round(total_usd, 4), "total_runs": total_runs}


def check_spending(client: httpx.Client) -> dict:
    """Check spending across multiple time periods."""
    now = datetime.now(timezone.utc)

    # Fetch up to 1000 runs to cover longer periods
    all_runs = []
    offset = 0
    limit = 1000
    try:
        resp = client.get("/v2/actor-runs", params={"limit": limit, "offset": offset, "desc": True})
        if resp.status_code == 200:
            all_runs = resp.json().get("data", {}).get("items", [])
    except Exception as e:
        return {"error": str(e)}

    # Determine billing period start from account info
    # Apify billing resets monthly; approximate as 1st of current month
    billing_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    periods = {
        "last_7_days": _aggregate_runs(all_runs, now - timedelta(days=7)),
        "last_30_days": _aggregate_runs(all_runs, now - timedelta(days=30)),
        "billing_period": _aggregate_runs(all_runs, billing_start),
        "year_to_date": _aggregate_runs(all_runs, year_start),
    }

    # Add metadata
    periods["billing_period_start"] = billing_start.isoformat()
    periods["year_start"] = year_start.isoformat()
    periods["runs_fetched"] = len(all_runs)

    return periods


def check_diagnostics() -> dict:
    """Check cost accuracy from _diagnostics table."""
    try:
        con = duckdb.connect(str(DB_PATH), read_only=True)
        result = con.execute("""
            SELECT
                COUNT(*) as total_jobs,
                AVG(CASE WHEN actual_cost > 0 THEN (actual_cost - estimated_cost) / actual_cost * 100 END) as avg_cost_error_pct,
                SUM(estimated_cost) as total_estimated,
                SUM(actual_cost) as total_actual,
                SUM(items_requested) as total_requested,
                SUM(items_returned) as total_returned
            FROM _diagnostics
            WHERE actual_cost IS NOT NULL
        """).fetchone()
        con.close()

        if result and result[0] > 0:
            return {
                "total_tracked_jobs": result[0],
                "avg_cost_error_pct": round(result[1], 1) if result[1] else None,
                "total_estimated_cost": round(result[2], 2) if result[2] else 0,
                "total_actual_cost": round(result[3], 2) if result[3] else 0,
                "total_items_requested": result[4] or 0,
                "total_items_returned": result[5] or 0,
                "item_fulfillment_rate": round(result[5] / result[4] * 100, 1) if result[4] and result[4] > 0 else None,
            }
        return {"total_tracked_jobs": 0, "note": "No completed jobs with cost tracking yet."}

    except Exception as e:
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Check Apify account health")
    parser.add_argument("--section", choices=["all", "account", "storage", "spending", "diagnostics"],
                        default="all", help="Which section to check")
    args = parser.parse_args()

    token = get_apify_token()
    client = httpx.Client(
        base_url="https://api.apify.com",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )

    report = {"timestamp": datetime.now(timezone.utc).isoformat()}

    sections = [args.section] if args.section != "all" else ["account", "storage", "spending", "diagnostics"]

    if "account" in sections:
        report["account"] = check_account_info(client)

    if "storage" in sections:
        report["storage"] = check_storage(client)

    if "spending" in sections:
        report["spending"] = check_spending(client)

    if "diagnostics" in sections:
        report["diagnostics"] = check_diagnostics()

    # Generate recommendations
    recommendations = []

    if "storage" in report:
        stale = report["storage"].get("stale_count", 0)
        if stale > 0:
            recommendations.append(
                f"Delete {stale} stale dataset(s) on Apify to reduce storage costs."
            )
        kv_stores = report["storage"].get("kv_stores", [])
        large_kv = [kv for kv in kv_stores if kv.get("size_bytes", 0) > 100 * 1024 * 1024]
        if large_kv:
            recommendations.append(
                f"{len(large_kv)} KV store(s) over 100MB — download locally and delete to save GB-hour costs."
            )

    if "account" in report:
        remaining = report["account"].get("balance_remaining_usd")
        if remaining is not None and remaining < 10:
            recommendations.append(
                f"Low account balance (${remaining:.2f} remaining). Consider upgrading plan."
            )

    if "diagnostics" in report:
        error_pct = report["diagnostics"].get("avg_cost_error_pct")
        if error_pct is not None and abs(error_pct) > 30:
            recommendations.append(
                f"Cost estimates are off by ~{abs(error_pct):.0f}% on average. Consider recalibrating."
            )

    report["recommendations"] = recommendations
    client.close()

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
