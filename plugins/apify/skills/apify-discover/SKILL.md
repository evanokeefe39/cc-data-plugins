---
name: apify-discover
description: >-
  This skill should be used when the user asks to "find an actor", "scrape [website]",
  "what can Apify scrape", "can Apify do", "I need data from", "explore Apify actors",
  "is there a scraper for", "what actors are available", "search Apify store",
  "discover scrapers", "how do I get data from", or wants to find Apify actors for a
  platform or data source not covered by the social media, e-commerce, or maps skills.
  Do NOT use when the user already knows which actor to use — use the domain-specific skill instead.
version: 0.1.0
compatibility: "Requires Python 3.11+, uv, and Apify MCP server (@apify/actors-mcp-server)"
metadata:
  author: cc-data-plugins
  mcp-server: apify
---

# Apify Actor Discovery

Find the right Apify actor for data extraction needs, especially for platforms and data sources beyond the core domains (social media, e-commerce, maps). Activate for platforms not covered by other skills (Reddit, LinkedIn, YouTube, Yelp, etc.), when the user doesn't know if Apify can handle their use case, or when an actor has been deprecated and an alternative is needed.

## CRITICAL: Packaged Scripts Only

NEVER write inline Python, ad-hoc DuckDB queries, or custom Bash. ALWAYS use `uv run scripts/<script>`. These are pre-authorized — inline code triggers permission prompts and breaks the flow.

## Four Gates (mandatory before any dispatch)

All four must pass. Enforced by skill instructions (soft), PreToolUse hook (hard), and script validation (hard).

1. **Params Complete** — All required params resolved, item limit set (`maxItems`/`resultsLimit`/etc.)
2. **Cost Approved** — `estimate_cost.py` run, estimate presented, user explicitly confirmed
3. **Scope Decided** — `metadata_only`, `with_media`, or `with_transcripts`
4. **Destination Set** — `local_duckdb`, `local_files`, `remote`, or `decide_later`

### Plan JSON format

Write to a `.json` file, pass via `--plan <file>`:
```json
{
  "session_id": "abc-123",
  "user_request": "Get 50 Reddit posts from r/technology",
  "jobs": [
    {
      "actor_id": "trudax/reddit-scraper",
      "input": {
        "searchTerms": ["r/technology"],
        "maxItems": 50
      }
    }
  ],
  "cost_approval": {
    "approved": true,
    "estimated_cost": 0.10,
    "timestamp": "2025-01-15T10:30:00Z"
  },
  "scope": "metadata_only",
  "destination": "local_duckdb"
}
```
- `jobs` is a **required array** — never put `actor_id` at top level
- `cost_approval` must have `approved: true` and `timestamp` (ISO-8601)
- Actor IDs use **slash notation** — dispatch script auto-converts to tilde

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

## Discovery Flow

### Step 1 — Check Local Registry First

Query the `_actor_registry` table in DuckDB for matching actors:
```
uv run $CLAUDE_PLUGIN_ROOTscripts/session_start.py --check-registry <query>
```

If the registry has a match, present it with known parameters and cost estimates.

### Step 2 — Search Apify Store via MCP

If the local registry doesn't have a match, use the Apify MCP server to search the actor store:
- Search by keyword (e.g., "reddit scraper", "youtube comments")
- Review results for reliability indicators: run count, user ratings, last update date, maintained by Apify vs. community

### Step 3 — Evaluate Actor Quality

Before recommending an actor, assess:

| Indicator | Good Sign | Warning Sign |
|-----------|-----------|--------------|
| Maintained by | `apify/` (official) | Unknown community developer |
| Last updated | Within 3 months | Over 6 months ago |
| Total runs | 1,000+ | Under 100 |
| User rating | 4.0+ stars | Under 3.0 stars |
| Documentation | Clear input/output schema | Sparse or missing docs |

### Step 4 — Present Recommendation

Present findings to the user:
1. Recommended actor with rationale
2. Required parameters (from actor docs)
3. Cost estimate from `estimate_cost.py` (if script returns `cost_unknown` for a new actor, tell the user — never guess)
4. Any warnings (community-maintained, infrequent updates, rental required)
5. Alternative actors if available

### Step 5 — Register for Future Use

After a successful run with a newly discovered actor, UPSERT into the `_actor_registry` table in DuckDB with:
- Actor ID, required/optional params, default maxItems
- Proxy type, $/1000 results (from actual run via `estimate_cost.py`)
- Output fields (from `_catalog` after import)

This ensures future runs skip discovery and go straight to planning.

## Common Discovery Requests

| User Asks About | Likely Actor | Notes |
|-----------------|-------------|-------|
| Reddit | `trudax/reddit-scraper` | Posts and comments |
| YouTube | `bernardo/youtube-scraper` | Videos, channels, comments |
| LinkedIn | Various | Most require auth — warn user |
| Yelp | `yin/yelp-scraper` | Business reviews |
| Zillow / Real Estate | `petr_cermak/zillow-scraper` | Property listings |
| News / Articles | `apify/website-content-crawler` | General web content |
| Any website | `apify/website-content-crawler` | Fallback for structured extraction |

These are starting points — always verify actor availability and current status via the Apify store.

## Examples

### Example 1: User wants Reddit data

User says: "Can Apify scrape Reddit posts?"

Actions:
1. Check local registry: `uv run scripts/session_start.py --check-registry reddit`
2. Registry has `trudax/reddit-scraper` — present actor with known params
3. User says "Get top 50 posts from r/technology"
4. Write plan with `searchTerms: ["r/technology"]`, `maxItems: 50`
5. Run `uv run scripts/estimate_cost.py --plan /tmp/plan.json` — returns `{"total_usd": 0.10, "source": "cached_registry"}`
6. Present plan with cost from script, get approval, dispatch

Result: 50 Reddit posts imported to DuckDB

### Example 2: Unknown platform — no cost data

User says: "Is there an Apify actor for Glassdoor reviews?"

Actions:
1. Check local registry — no match
2. Search Apify MCP store for "glassdoor reviews"
3. Find `misceres/glassdoor-scraper` — community actor, 500 runs, 3.8 stars, updated 2 months ago
4. Run `estimate_cost.py` — returns `{"cost_unknown": true, "error": "No cost data available..."}`
5. Present: "Found a community actor for Glassdoor. No cost data yet — suggest a small test run of 10 items first to establish pricing."
6. User agrees → dispatch small test, then register actor for future use

Result: Actor tested, cost data cached, ready for larger runs

## Important Caveats

- **Actor availability changes**: Actors can be deprecated, renamed, or removed. Always verify current status
- **Community actors**: Less reliable than official Apify actors. Set expectations accordingly
- **Rental actors**: Some actors require monthly subscriptions. Always warn before recommending
- **Rate limits**: Unknown actors may have undocumented rate limits. Start with small `maxItems` for first runs
- **Output schema**: Unknown until first run. Plan for schema discovery during import

## After Discovery

Once an actor is selected, hand off to the standard four-gate planning flow:
1. Resolve all required parameters
2. Estimate cost
3. Get scope and destination approval
4. Dispatch via `run_actors.py`
