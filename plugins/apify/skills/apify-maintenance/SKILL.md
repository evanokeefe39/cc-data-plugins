---
name: apify-maintenance
description: >-
  This skill should be used when the user asks to "check storage costs", "clean up Apify data",
  "check account health", "review spending", "delete old datasets", "check my Apify usage",
  "how much am I spending", "how many credits left", "check my credits", "billing report",
  "storage cleanup", "consumption report", "purge old data", or mentions
  Apify storage, costs, credits, spending, cleanup, or account maintenance.
  Do NOT use for data extraction — use the domain-specific skills instead.
version: 0.1.0
---

# Apify Maintenance & Account Health

Monitor Apify account health, track spending, manage storage costs, and clean up stale data. This skill covers everything that isn't data extraction — the operational overhead of running Apify jobs.

For lifecycle rules, four-gate enforcement, data handling rules, and script reference, consult `../shared/plugin-rules.md`.

## Health Check Flow

Run the account health check:
```
uv run $CLAUDE_PLUGIN_ROOTscripts/check_account_health.py
```

This script checks:
1. **Credit balance** — current credits remaining, burn rate
2. **Storage usage** — datasets, KV stores, request queues
3. **Stale datasets** — datasets older than 7 days still on Apify (accumulating storage costs)
4. **KV store costs** — GB-hours for any media files still stored on Apify
5. **Recent spending** — last 7 days of credit consumption by actor

### Output Format

Adapts to user profile:

**Non-technical:**
```
Your Apify account summary:
- Credits remaining: 42.5 (about 2 weeks at current pace)
- Storage: 3 old datasets still on Apify, costing ~0.2 credits/day
- Recommendation: Download and delete 2 video datasets to save costs
```

**Technical:**
```
Credits: 42.5 remaining | 7d burn: 18.3 | projected runway: 16d
Storage: 3 datasets (2.1 GB), 1 KV store (450 MB @ 0.08 credits/GB-hr)
Stale: dataset_abc123 (12d, 1.8 GB), dataset_def456 (8d, 300 MB)
Action: Recommend purging stale datasets (-0.2 credits/day)
```

## Cost Tracking

Query `_diagnostics` for estimated vs. actual costs per job:

| Field | Description |
|-------|-------------|
| `estimated_cost` | Pre-run estimate from `estimate_cost.py` |
| `actual_cost` | Post-run actual from Apify API |
| `items_requested` | maxItems in the plan |
| `items_returned` | Actual items received |

Over time, this builds a cost accuracy model. Surface trends:
- "Your Instagram estimates are consistently 20% low — adjusting future estimates"
- "TikTok video downloads cost 3x more than metadata — consider metadata_only scope"

## Storage Cleanup

### Stale Dataset Cleanup

1. Query DuckDB: `uv run $CLAUDE_PLUGIN_ROOTscripts/query_dataset.py sql "SELECT * FROM landed_data"`
2. Cross-reference with Apify storage to find datasets downloaded locally AND still on Apify
3. Present list to user with sizes and daily storage costs
4. **Never auto-delete** — always ask for confirmation
5. Delete via Apify REST API as a separate Claude Task

### KV Store Cleanup

KV stores accumulate GB-hour charges for media files (images, videos):
1. Run `uv run $CLAUDE_PLUGIN_ROOTscripts/check_account_health.py --section storage` to list KV stores
2. For stores where media has been downloaded locally: recommend deletion
3. Warn about stores growing over time if jobs are still writing to them

## Spending Trends

Run `uv run $CLAUDE_PLUGIN_ROOTscripts/check_account_health.py --section spending` or query `_diagnostics` directly to show:
- Credits consumed per day/week/month
- Breakdown by actor (which actors cost the most)
- Breakdown by platform (Instagram vs. TikTok vs. Amazon)
- Cost efficiency: credits per 100 items by actor
- Trend direction: spending increasing, decreasing, or stable

## Maintenance Checklist

Present as a periodic health review:

- [ ] Credit balance sufficient for planned work
- [ ] No stale datasets accumulating storage costs
- [ ] No orphaned KV stores from media downloads
- [ ] Actor registry up to date (< 24h old)
- [ ] Cost estimates calibrated against actuals
- [ ] No failed jobs left unresolved in DuckDB

## Additional Resources

### Reference Files

- **`../shared/plugin-rules.md`** — Full script reference, lifecycle rules, four-gate enforcement
