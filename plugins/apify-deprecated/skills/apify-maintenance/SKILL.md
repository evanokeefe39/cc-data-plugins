---
name: apify-maintenance
description: >-
  This skill should be used when the user asks to "check storage costs", "clean up Apify data",
  "check account health", "review spending", "delete old datasets", "check my Apify usage",
  "how much am I spending", "how much balance left", "check my balance", "billing report",
  "storage cleanup", "consumption report", "purge old data", or mentions
  Apify storage, costs, spending, cleanup, or account maintenance.
  Do NOT use for data extraction — use the domain-specific skills instead.
version: 0.1.0
compatibility: "Requires Python 3.11+, uv, and Apify MCP server (@apify/actors-mcp-server)"
metadata:
  author: cc-data-plugins
  mcp-server: apify
---

# Apify Maintenance & Account Health

Monitor Apify account health, track spending, manage storage costs, and clean up stale data. This skill covers everything that isn't data extraction — the operational overhead of running Apify jobs.

## CRITICAL: Packaged Scripts Only

NEVER write inline Python, ad-hoc DuckDB queries, or custom Bash. ALWAYS use `uv run "$CLAUDE_PLUGIN_ROOT/scripts/<script>"`. These are pre-authorized — inline code triggers permission prompts and breaks the flow.

## Four Gates (mandatory before any dispatch)

All four must pass. Enforced by skill instructions (soft), PreToolUse hook (hard), and script validation (hard).

1. **Params Complete** — All required params resolved, item limit set (`maxItems`/`resultsLimit`/etc.)
2. **Cost Approved** — `estimate_cost.py` run, estimate presented, user explicitly confirmed
3. **Scope Decided** — `metadata_only`, `with_media`, or `with_transcripts`
4. **Destination Set** — `local_duckdb`, `local_files`, `remote`, or `decide_later`

## Cost Estimation — Hard Rule

**NEVER invent, guess, or hallucinate cost numbers.** Run `estimate_cost.py` — it returns costs in **USD**. If you cannot run the script, say so — never fill in placeholder numbers. The word "credits" is wrong — Apify bills in USD.

## Data Handling Rules

- Data NEVER passes through the LLM context — scripts stream to files, import to DuckDB
- Check existing data BEFORE proposing any new scrape
- Never auto-delete from Apify — always ask first
- Retries go through all four gates again (a retry is a new plan)

## Script Reference

| Script | Purpose | Key Args |
|--------|---------|----------|
| `session_start.py` | Init, recovery, registry refresh | `--force-refresh`, `--check-registry <query>` |
| `run_actors.py dispatch` | Dispatch jobs (validates 4 gates) | `--plan <file>` |
| `run_actors.py poll` | Check running job status | `--run-id <id>` |
| `estimate_cost.py` | Cost estimate from Apify API | `--plan <file>` |
| `fetch_dataset.py` | Stream dataset to local files | `--dataset-id <id>`, `--format jsonl\|csv` |
| `import_dataset.py` | Import into DuckDB | `--file <path>`, `--actor-slug <actor>` |
| `query_dataset.py sql` | Query DuckDB | `"<SQL>"`, `--limit <n>` |
| `query_dataset.py tables` | List all DuckDB tables | — |
| `check_account_health.py` | Storage, spending, diagnostics | `--section all\|account\|storage\|spending` |

For user profile handling, auth setup, and full lifecycle details, see `../shared/plugin-rules.md`.

## Health Check Flow

Run the account health check:
```
uv run "$CLAUDE_PLUGIN_ROOT/scripts/check_account_health.py"
```

This script checks:
1. **Account balance** — current USD balance remaining, burn rate
2. **Storage usage** — datasets, KV stores, request queues
3. **Stale datasets** — datasets older than 7 days still on Apify (accumulating storage costs)
4. **KV store costs** — GB-hours for any media files still stored on Apify
5. **Recent spending** — last 7 days of USD consumption by actor

### Output Format

Adapts to user profile:

**Non-technical:**
```
Your Apify account summary:
- Balance remaining: $42.50 (about 2 weeks at current pace)
- Storage: 3 old datasets still on Apify, costing ~$0.20/day
- Recommendation: Download and delete 2 video datasets to save costs
```

**Technical:**
```
Balance: $42.50 remaining | 7d burn: $18.30 | projected runway: 16d
Storage: 3 datasets (2.1 GB), 1 KV store (450 MB @ $0.08/GB-hr)
Stale: dataset_abc123 (12d, 1.8 GB), dataset_def456 (8d, 300 MB)
Action: Recommend purging stale datasets (-$0.20/day)
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

1. Query DuckDB: `uv run "$CLAUDE_PLUGIN_ROOT/scripts/query_dataset.py" sql "SELECT * FROM landed_data"`
2. Cross-reference with Apify storage to find datasets downloaded locally AND still on Apify
3. Present list to user with sizes and daily storage costs
4. **Never auto-delete** — always ask for confirmation
5. Delete via Apify REST API as a separate Claude Task

### KV Store Cleanup

KV stores accumulate GB-hour charges for media files (images, videos):
1. Run `uv run "$CLAUDE_PLUGIN_ROOT/scripts/check_account_health.py" --section storage` to list KV stores
2. For stores where media has been downloaded locally: recommend deletion
3. Warn about stores growing over time if jobs are still writing to them

## Spending Trends

Run `uv run "$CLAUDE_PLUGIN_ROOT/scripts/check_account_health.py" --section spending` or query `_diagnostics` directly to show:
- USD consumed per day/week/month
- Breakdown by actor (which actors cost the most)
- Breakdown by platform (Instagram vs. TikTok vs. Amazon)
- Cost efficiency: $/1000 results by actor (from `estimate_cost.py`)
- Trend direction: spending increasing, decreasing, or stable

## Examples

### Example 1: Routine health check

User says: "How's my Apify account looking?"

Actions:
1. Run `uv run "$CLAUDE_PLUGIN_ROOT/scripts/check_account_health.py" --section all`
2. Script returns: balance $42.50, 3 stale datasets (2.1 GB), 7-day burn $18.30
3. Present summary adapted to user profile (technical vs. non-technical)
4. Recommend: "You have 3 old datasets still on Apify costing ~$0.20/day. Want me to list them for cleanup?"

Result: User gets clear picture of account status with actionable recommendations

### Example 2: Cost accuracy review

User says: "Are my cost estimates accurate?"

Actions:
1. Run `uv run "$CLAUDE_PLUGIN_ROOT/scripts/query_dataset.py" sql "SELECT actor_id, AVG(estimated_cost), AVG(actual_cost) FROM _diagnostics GROUP BY actor_id"`
2. Compare estimated vs. actual per actor
3. Present: "Instagram estimates are 15% low on average. TikTok video downloads cost 3x more than metadata-only runs."

Result: User understands cost trends, can adjust future planning

## Maintenance Checklist

Present as a periodic health review:

- [ ] Account balance sufficient for planned work
- [ ] No stale datasets accumulating storage costs
- [ ] No orphaned KV stores from media downloads
- [ ] Actor registry up to date (< 24h old)
- [ ] Cost estimates calibrated against actuals
- [ ] No failed jobs left unresolved in DuckDB

## Additional Resources

### Reference Files

- **`../shared/plugin-rules.md`** — Full script reference, lifecycle rules, four-gate enforcement
