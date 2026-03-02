# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.1.0",
#     "httpx>=0.27.0",
# ]
# ///
"""
Cost estimation script — queries Apify API for exact cost estimates.

Three-tier estimation (in priority order):
1. Live API — query /acts/{id}/runs for recent cost data
2. Cached registry — read cost_per_100_usd from _actor_registry in DuckDB
3. Hardcoded fallback — last resort, may be inaccurate

Used in Normal Mode (not Plan Mode, where skill-embedded tables provide rough estimates).
Estimates compute cost, proxy cost, and any rental fees.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import duckdb
import httpx

APIFY_API_BASE = "https://api.apify.com/v2"

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd()))
DATA_DIR = PROJECT_DIR / ".apify_plugin" / "data"
DB_PATH = DATA_DIR / "datasets.duckdb"

# Rough cost multipliers when API data is unavailable (last resort)
FALLBACK_COSTS = {
    # actor_id_prefix -> USD per 100 items (rough)
    "apify/instagram": 1.5,
    "clockworks/tiktok": 2.0,
    "apidojo/tweet": 1.0,
    "apify/facebook": 2.0,
    "junglee/amazon": 3.0,
    "piotrv1001/walmart": 2.0,
    "autofacts/shopify": 1.5,
    "apify/e-commerce": 2.5,
    "compass/crawler-google": 2.0,
    "compass/Google-Maps": 1.5,
}

# Proxy costs per GB
PROXY_COSTS = {
    "residential": 12.5,  # credits per GB
    "datacenter": 0.5,    # credits per GB
}

# Actors known to require residential proxies
RESIDENTIAL_PROXY_ACTORS = {
    "apify/instagram-scraper",
    "clockworks/tiktok-scraper",
    "apify/facebook-posts-scraper",
    "junglee/amazon-crawler",
    "piotrv1001/walmart-listings-scraper",
}


def get_apify_token() -> str:
    from _token import get_apify_token as _get
    token = _get()
    if not token:
        print(json.dumps({"error": "No APIFY_TOKEN set. Using fallback estimates only."}))
    return token or ""


def get_fallback_cost(actor_id: str) -> float:
    """Get rough cost per 100 items from hardcoded fallback table."""
    for prefix, cost in FALLBACK_COSTS.items():
        if actor_id.lower().startswith(prefix.lower()):
            return cost
    return 2.0  # default fallback


def get_cached_registry_cost(actor_id: str) -> tuple[float | None, str | None]:
    """Get cost_per_100_usd from _actor_registry in DuckDB.

    Returns (cost_per_100_usd, refreshed_at_str) or (None, None) if unavailable.
    """
    if not DB_PATH.exists():
        return None, None
    try:
        con = duckdb.connect(str(DB_PATH), read_only=True)
        result = con.execute(
            "SELECT cost_per_100_usd, refreshed_at FROM _actor_registry WHERE actor_id = ?",
            [actor_id],
        ).fetchone()
        con.close()
        if result and result[0] is not None:
            refreshed_at = str(result[1]).split("T")[0] if result[1] else "unknown"
            return result[0], refreshed_at
    except Exception:
        pass
    return None, None


def get_cached_proxy_type(actor_id: str) -> str | None:
    """Get proxy_type from _actor_registry in DuckDB."""
    if not DB_PATH.exists():
        return None
    try:
        con = duckdb.connect(str(DB_PATH), read_only=True)
        result = con.execute(
            "SELECT proxy_type FROM _actor_registry WHERE actor_id = ?",
            [actor_id],
        ).fetchone()
        con.close()
        if result and result[0]:
            return result[0]
    except Exception:
        pass
    return None


def estimate_job(actor_id: str, input_params: dict, scope: str, token: str) -> dict:
    """Estimate cost for a single job using three-tier pricing."""
    max_items = (
        input_params.get("maxItems") or
        input_params.get("resultsLimit") or
        input_params.get("resultsPerPage") or
        input_params.get("maxCrawledPlacesPerSearch") or
        100
    )

    estimate = {
        "actor_id": actor_id,
        "max_items": max_items,
        "scope": scope,
        "breakdown": {},
    }

    # Three-tier cost resolution
    cost_per_100 = None
    source = None

    # Tier 1: Live API
    if token:
        client = httpx.Client(
            base_url=APIFY_API_BASE,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        try:
            resp = client.get(f"/acts/{actor_id}/runs", params={"limit": 5, "desc": True})
            if resp.status_code == 200:
                runs = resp.json().get("data", {}).get("items", [])
                if runs:
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
                            cost_per_100 = (total_cost / total_items) * 100
                            source = "historical_runs"

            # Check for rental pricing
            resp = client.get(f"/acts/{actor_id}")
            if resp.status_code == 200:
                actor_data = resp.json().get("data", {})
                pricing = actor_data.get("pricing", {})
                if pricing.get("pricingModel") == "FLAT_PRICE_PER_MONTH":
                    estimate["rental_warning"] = {
                        "monthly_cost_usd": pricing.get("pricePerUnitUsd", 0),
                        "message": f"This actor requires a monthly rental of ${pricing.get('pricePerUnitUsd', '?')}/month",
                    }

        except Exception:
            pass
        finally:
            client.close()

    # Tier 2: Cached registry
    if cost_per_100 is None:
        cached_cost, refreshed_at = get_cached_registry_cost(actor_id)
        if cached_cost is not None:
            cost_per_100 = cached_cost
            source = "cached_registry"
            estimate["is_fallback"] = True
            estimate["fallback_note"] = (
                f"* Couldn't fetch latest prices. Using last known costs as at {refreshed_at}."
            )

    # Tier 3: Hardcoded fallback
    if cost_per_100 is None:
        cost_per_100 = get_fallback_cost(actor_id)
        source = "fallback_table"
        estimate["is_fallback"] = True
        estimate["fallback_note"] = (
            "* Couldn't fetch latest prices. Using hardcoded estimates (may be inaccurate)."
        )

    estimate["source"] = source

    # Calculate compute cost (cost_per_100 is now in USD)
    compute_usd = (max_items / 100) * cost_per_100
    estimate["breakdown"]["compute_usd"] = round(compute_usd, 4)

    # Proxy cost estimate
    cached_proxy = get_cached_proxy_type(actor_id)
    proxy_type = cached_proxy or ("residential" if actor_id in RESIDENTIAL_PROXY_ACTORS else "datacenter")
    # Rough: ~1 MB per 100 items for metadata, ~50 MB for media
    mb_per_100 = 1 if scope == "metadata_only" else 50
    proxy_gb = (max_items / 100) * mb_per_100 / 1024
    proxy_credits = proxy_gb * PROXY_COSTS[proxy_type]
    estimate["breakdown"]["proxy"] = round(proxy_credits, 2)
    estimate["breakdown"]["proxy_type"] = proxy_type

    # Media download cost (if scope includes media)
    if scope in ("with_media", "with_transcripts"):
        media_credits = (max_items / 100) * 5  # rough: 5 credits per 100 media items
        estimate["breakdown"]["media_download"] = round(media_credits, 2)
    else:
        estimate["breakdown"]["media_download"] = 0

    # Total
    total = sum(v for k, v in estimate["breakdown"].items() if isinstance(v, (int, float)))
    estimate["total_credits"] = round(total, 2)
    estimate["estimated_time_minutes"] = max(1, int(max_items / 50))  # rough: 50 items/minute

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

    estimates = []
    for job in plan.get("jobs", []):
        est = estimate_job(
            actor_id=job["actor_id"],
            input_params=job.get("input", {}),
            scope=scope,
            token=token,
        )
        estimates.append(est)

    total_credits = sum(e["total_credits"] for e in estimates)
    total_time = sum(e["estimated_time_minutes"] for e in estimates)

    has_fallbacks = any(e.get("is_fallback") for e in estimates)

    output = {
        "jobs": estimates,
        "summary": {
            "total_credits": round(total_credits, 2),
            "estimated_time_minutes": total_time,
            "job_count": len(estimates),
            "scope": scope,
        },
        "approval_prompt": (
            f"Estimated cost: ~{total_credits:.1f} credits across {len(estimates)} job(s). "
            f"Estimated time: ~{total_time} minutes. "
            f"Scope: {scope}. "
            "Approve this plan?"
        ),
    }

    if has_fallbacks:
        output["summary"]["has_fallbacks"] = True

    # Add rental warnings if any
    rentals = [e for e in estimates if "rental_warning" in e]
    if rentals:
        output["rental_warnings"] = [e["rental_warning"] for e in rentals]

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
