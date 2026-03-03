# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.1.0",
#     "httpx>=0.27.0",
# ]
# ///
"""
Cost estimation script — queries Apify API for real cost data.

Two-tier estimation (in priority order):
1. Live API — query /acts/{id}/runs for recent cost-per-item from real runs
2. Cached registry — read cost_per_1000_usd from _actor_registry in DuckDB

No hardcoded fallbacks. If real data is unavailable, the estimate reports
"unknown" so the user can decide whether to proceed.

When Tier 1 succeeds, results are cached back to _actor_registry for future use.

Note: Apify quotes costs as $/1000 results. All internal calculations use this unit.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import httpx

APIFY_API_BASE = "https://api.apify.com/v2"

def _resolve_project_dir() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    cwd = Path.cwd()
    if (cwd / ".apify_plugin").exists():
        return cwd
    print(json.dumps({"error": "CLAUDE_PROJECT_DIR not set and .apify_plugin/ not found in cwd", "cwd": str(cwd)}), file=sys.stderr)
    sys.exit(1)

PROJECT_DIR = _resolve_project_dir()
DATA_DIR = PROJECT_DIR / ".apify_plugin" / "data"
DB_PATH = DATA_DIR / "datasets.duckdb"


def get_apify_token() -> str:
    from _token import get_apify_token as _get
    token = _get()
    if not token:
        print(json.dumps({"error": "No APIFY_TOKEN set. Cannot fetch live pricing."}),
              file=sys.stderr)
    return token or ""


def _get_cost_column(con: duckdb.DuckDBPyConnection) -> tuple[str, float]:
    """Detect whether DB uses new cost_per_1000_usd or legacy cost_per_100_usd column.

    Returns (column_name, multiplier_to_per_1000).
    """
    cols = [row[1] for row in con.execute("PRAGMA table_info('_actor_registry')").fetchall()]
    if "cost_per_1000_usd" in cols:
        return "cost_per_1000_usd", 1.0
    return "cost_per_100_usd", 10.0


def get_cached_registry_cost(actor_id: str) -> tuple[float | None, str | None, int]:
    """Get cost_per_1000_usd from _actor_registry in DuckDB.

    Returns (cost_per_1000_usd, refreshed_at_str, sample_runs) or (None, None, 0).
    Falls back to reading legacy cost_per_100_usd column and converting.
    """
    if not DB_PATH.exists():
        return None, None, 0
    try:
        con = duckdb.connect(str(DB_PATH), read_only=True)
        col, multiplier = _get_cost_column(con)
        result = con.execute(
            f"SELECT {col}, refreshed_at, cost_sample_runs FROM _actor_registry WHERE actor_id = ?",
            [actor_id],
        ).fetchone()
        con.close()
        if result and result[0] is not None:
            refreshed_at = str(result[1]).split("T")[0] if result[1] else "unknown"
            sample_runs = result[2] or 0
            return result[0] * multiplier, refreshed_at, sample_runs
    except Exception:
        pass
    return None, None, 0


def cache_cost_to_registry(actor_id: str, cost_per_1000: float, sample_runs: int):
    """Write live cost data back to _actor_registry for future lookups."""
    if not DB_PATH.exists():
        return
    try:
        con = duckdb.connect(str(DB_PATH))
        now = datetime.now(timezone.utc).isoformat()
        col, multiplier = _get_cost_column(con)
        # Store in whichever column exists (convert back if legacy)
        store_value = cost_per_1000 / multiplier
        con.execute(f"""
            UPDATE _actor_registry
            SET {col} = ?, cost_sample_runs = ?, refreshed_at = ?
            WHERE actor_id = ?
        """, [store_value, sample_runs, now, actor_id])
        con.close()
    except Exception:
        pass


def _count_input_targets(input_params: dict) -> int:
    """Count number of profiles/URLs/search terms in input params."""
    for key in ("profiles", "directUrls", "startUrls", "twitterHandles",
                "searchTerms", "hashtags", "urls", "queries"):
        val = input_params.get(key)
        if isinstance(val, list) and len(val) > 0:
            return len(val)
    return 1


def _fetch_live_cost(actor_id: str, token: str, client: httpx.Client) -> tuple[float | None, int, dict | None]:
    """Fetch cost per 1000 results from recent Apify runs.

    Returns (cost_per_1000_usd, sample_count, rental_warning_or_none).
    """
    api_actor_id = actor_id.replace("/", "~")
    cost_per_1000 = None
    sample_count = 0
    rental_warning = None

    try:
        resp = client.get(f"/acts/{api_actor_id}/runs", params={"limit": 10, "desc": True})
        if resp.status_code == 200:
            runs = resp.json().get("data", {}).get("items", [])
            costs = []
            for run in runs:
                usage_usd = run.get("usageTotalUsd")
                items = run.get("stats", {}).get("itemsCount", 0)
                if usage_usd and items and items > 0:
                    costs.append((usage_usd, items))

            if costs:
                total_cost = sum(c[0] for c in costs)
                total_items = sum(c[1] for c in costs)
                if total_items > 0:
                    cost_per_1000 = round((total_cost / total_items) * 1000, 4)
                    sample_count = len(costs)

        # Check for rental pricing
        resp = client.get(f"/acts/{api_actor_id}")
        if resp.status_code == 200:
            actor_data = resp.json().get("data", {})
            pricing = actor_data.get("pricing", {})
            if pricing.get("pricingModel") == "FLAT_PRICE_PER_MONTH":
                rental_warning = {
                    "monthly_cost_usd": pricing.get("pricePerUnitUsd", 0),
                    "message": f"This actor requires a monthly rental of ${pricing.get('pricePerUnitUsd', '?')}/month",
                }

    except Exception:
        pass

    return cost_per_1000, sample_count, rental_warning


def estimate_job(actor_id: str, input_params: dict, scope: str, token: str,
                 client: httpx.Client | None) -> dict:
    """Estimate cost for a single job using real pricing data only."""
    items_per_target = (
        input_params.get("maxItems") or
        input_params.get("resultsLimit") or
        input_params.get("resultsPerPage") or
        input_params.get("maxCrawledPlacesPerSearch") or
        100
    )

    target_count = _count_input_targets(input_params)
    max_items = items_per_target * target_count

    estimate = {
        "actor_id": actor_id,
        "target_count": target_count,
        "items_per_target": items_per_target,
        "max_items": max_items,
        "scope": scope,
        "breakdown": {},
    }

    # Two-tier cost resolution — no hardcoded fallback
    cost_per_1000 = None
    source = None
    sample_runs = 0

    # Tier 1: Live API
    if token and client:
        cost_per_1000, sample_runs, rental_warning = _fetch_live_cost(actor_id, token, client)
        if cost_per_1000 is not None:
            source = "live_api"
            estimate["sample_runs"] = sample_runs
            # Cache for future use
            cache_cost_to_registry(actor_id, cost_per_1000, sample_runs)
        if rental_warning:
            estimate["rental_warning"] = rental_warning

    # Tier 2: Cached registry
    if cost_per_1000 is None:
        cached_cost, refreshed_at, cached_samples = get_cached_registry_cost(actor_id)
        if cached_cost is not None:
            cost_per_1000 = cached_cost
            source = "cached_registry"
            sample_runs = cached_samples
            estimate["sample_runs"] = cached_samples
            estimate["cache_note"] = (
                f"Using cached cost data from {refreshed_at} ({cached_samples} sample runs)."
            )

    # No data available — report unknown
    if cost_per_1000 is None:
        estimate["source"] = "none"
        estimate["cost_unknown"] = True
        estimate["error"] = (
            f"No cost data available for {actor_id}. "
            "Run this actor at least once, or ensure the actor registry has been refreshed "
            "(session_start.py --force-refresh)."
        )
        estimate["total_usd"] = None
        estimate["estimated_time_minutes"] = max(1, int(max_items / 50))
        return estimate

    estimate["source"] = source
    estimate["cost_per_1000_usd"] = cost_per_1000

    # Calculate cost (all-in USD — proxy already included in per-result pricing)
    compute_usd = (max_items / 1000) * cost_per_1000
    estimate["breakdown"]["compute_usd"] = round(compute_usd, 4)

    # Media download cost (if scope includes media)
    if scope in ("with_media", "with_transcripts"):
        media_usd = (max_items / 1000) * 10.0  # ~$10.00 per 1000 media items
        estimate["breakdown"]["media_download_usd"] = round(media_usd, 2)
    else:
        estimate["breakdown"]["media_download_usd"] = 0

    # Total
    total = sum(v for k, v in estimate["breakdown"].items() if isinstance(v, (int, float)))
    estimate["total_usd"] = round(total, 2)
    estimate["estimated_time_minutes"] = max(1, int(max_items / 50))

    return estimate


def main():
    parser = argparse.ArgumentParser(description="Estimate Apify job costs")
    parser.add_argument("--plan", required=True, help="Plan JSON file path or inline JSON")
    args = parser.parse_args()

    plan_input = args.plan
    if os.path.isfile(plan_input):
        plan = json.loads(Path(plan_input).read_text(encoding="utf-8"))
    else:
        plan = json.loads(plan_input)

    token = get_apify_token()
    scope = plan.get("scope", "metadata_only")

    # Create shared HTTP client for all jobs
    client = None
    if token:
        client = httpx.Client(
            base_url=APIFY_API_BASE,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )

    estimates = []
    for job in plan.get("jobs", []):
        est = estimate_job(
            actor_id=job["actor_id"],
            input_params=job.get("input", {}),
            scope=scope,
            token=token,
            client=client,
        )
        estimates.append(est)

    if client:
        client.close()

    # Check for unknown costs
    unknown_jobs = [e for e in estimates if e.get("cost_unknown")]
    known_jobs = [e for e in estimates if not e.get("cost_unknown")]

    total_usd = sum(e["total_usd"] for e in known_jobs) if known_jobs else None
    total_time = sum(e["estimated_time_minutes"] for e in estimates)

    output = {
        "jobs": estimates,
        "summary": {
            "total_usd": round(total_usd, 2) if total_usd is not None else None,
            "estimated_time_minutes": total_time,
            "job_count": len(estimates),
            "scope": scope,
        },
    }

    if unknown_jobs:
        output["summary"]["unknown_cost_jobs"] = len(unknown_jobs)
        output["summary"]["warning"] = (
            f"{len(unknown_jobs)} job(s) have no cost data. "
            "Run session_start.py --force-refresh to populate the actor registry, "
            "or run a small test job first."
        )

    if total_usd is not None and not unknown_jobs:
        output["approval_prompt"] = (
            f"Estimated cost: ~${total_usd:.2f} USD across {len(estimates)} job(s). "
            f"Estimated time: ~{total_time} minutes. "
            f"Scope: {scope}. "
            "Approve this plan?"
        )
    elif total_usd is not None and unknown_jobs:
        output["approval_prompt"] = (
            f"Partial estimate: ~${total_usd:.2f} USD for {len(known_jobs)} job(s) "
            f"({len(unknown_jobs)} job(s) have unknown cost). "
            f"Estimated time: ~{total_time} minutes. "
            f"Scope: {scope}. "
            "Approve this plan?"
        )
    else:
        output["approval_prompt"] = (
            f"Cannot estimate cost — no pricing data for any job. "
            "Run session_start.py --force-refresh to populate the actor registry."
        )

    # Add rental warnings if any
    rentals = [e for e in estimates if "rental_warning" in e]
    if rentals:
        output["rental_warnings"] = [e["rental_warning"] for e in rentals]

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
