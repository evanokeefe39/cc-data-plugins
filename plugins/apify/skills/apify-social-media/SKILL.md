---
name: apify-social-media
description: >-
  This skill should be used when the user asks to "scrape Instagram", "get TikTok posts",
  "extract Twitter data", "download Facebook posts", "get social media profiles",
  "scrape followers", "get engagement metrics", "download reels", "scrape hashtags",
  "scrape comments", "get replies", "scrape social media data",
  or mentions Instagram, TikTok, Twitter/X, or Facebook in the context of data extraction.
  Do NOT use for analyzing or visualizing social data — only for extracting it from platforms via Apify.
version: 0.1.0
compatibility: "Requires Python 3.11+, uv, and Apify MCP server (@apify/actors-mcp-server)"
metadata:
  author: cc-data-plugins
  mcp-server: apify
---

# Apify Social Media Extraction

Extract posts, profiles, and engagement data from Instagram, TikTok, Twitter/X, and Facebook using Apify actors.

## CRITICAL: Packaged Scripts Only

NEVER write inline Python, ad-hoc DuckDB queries, or custom Bash. ALWAYS use `uv run "$CLAUDE_PLUGIN_ROOT/scripts/<script>"`. These are pre-authorized — inline code triggers permission prompts and breaks the flow.

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
  "user_request": "Get 50 Instagram posts from @natgeo",
  "jobs": [
    {
      "actor_id": "apify/instagram-scraper",
      "input": {
        "directUrls": ["https://www.instagram.com/natgeo/"],
        "resultsType": "posts",
        "resultsLimit": 50
      }
    }
  ],
  "cost_approval": {
    "approved": true,
    "estimated_cost": 0.12,
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

## Planning Flow

1. Check existing data first — run `uv run "$CLAUDE_PLUGIN_ROOT/scripts/query_dataset.py" sql "SELECT * FROM landed_data"` to check for relevant data already downloaded. If local data answers the question, query it directly — no scrape needed
2. Identify the target platform and content type from the user's request
3. Select the correct actor from the actor table (see `references/actor-tables.md`)
4. Resolve all required parameters — ask the user for any missing inputs (profile URLs, hashtags, search terms)
5. Set `maxItems` — never leave unbounded. Default to 100 unless the user specifies otherwise
6. Check `_catalog` for known output fields for this actor. If known, summarize available fields so the user can make informed scope decisions
7. **Estimate cost** — STOP and run `estimate_cost.py --plan <plan.json>` before presenting costs to the user. Never write cost numbers (USD or otherwise) without script output. Never use the word "credits" — Apify costs are in USD. If the script returns `cost_unknown`, tell the user no cost data is available yet
8. Present the full execution plan for four-gate approval — cost numbers in the plan MUST come from step 7's script output

## Social Media Specific Rules

### Pinned Posts

Exclude pinned posts by default — they skew engagement metrics and recency filters. Include only when the user explicitly requests them.

### Default Media Behavior

Default to downloading media locally rather than storing in Apify KV. KV storage incurs GB-hour costs. On first media download, ask the user for their preference and store it in the `_user_config` table in DuckDB.

## Actor Quick Reference

| Platform | Actor ID | Required Params |
|----------|----------|-----------------|
| Instagram | `apify/instagram-scraper` | `directUrls` |
| TikTok | `clockworks/tiktok-scraper` | `profiles` or `hashtags` |
| Twitter/X | `apidojo/tweet-scraper` | `searchTerms` or `twitterHandles` |
| Facebook | `apify/facebook-posts-scraper` | `startUrls` |

**Costs**: You MUST run `estimate_cost.py --plan <file>` to get real USD pricing. Never write cost numbers without running the script first. Never use the term "credits".

For complete actor parameters, cost models, and platform-specific notes, consult `references/actor-tables.md`.

## Cross-Platform Field Mapping

Different platforms use different names for the same metrics:

| Concept | Instagram | TikTok | Twitter/X | Facebook |
|---------|-----------|--------|-----------|----------|
| Likes | `likesCount` | `diggCount` | `likeCount` | `likes` |
| Comments | `commentsCount` | `commentCount` | `replyCount` | `comments` |
| Shares | — | `shareCount` | `retweetCount` | `shares` |
| Views | `videoViewCount` | `playCount` | `viewCount` | `views` |

For cross-platform "engagement data" requests, note these field differences in the execution plan.

## Examples

### Example 1: Scrape latest posts from a creator

User says: "Get me the last 20 posts from @natgeo on Instagram"

Actions:
1. Check existing data: `uv run "$CLAUDE_PLUGIN_ROOT/scripts/query_dataset.py" sql "SELECT * FROM landed_data WHERE source LIKE '%natgeo%'"`
2. No local data found — select actor `apify/instagram-scraper`
3. Write plan JSON with `directUrls: ["https://www.instagram.com/natgeo/"]`, `resultsLimit: 20`, `resultsType: "posts"`
4. Run `uv run "$CLAUDE_PLUGIN_ROOT/scripts/estimate_cost.py" --plan /tmp/plan.json` — script returns `{"total_usd": 0.08, "source": "live_api"}`
5. Present plan: "20 posts from @natgeo, estimated cost ~$0.08 USD, metadata only, local DuckDB. Approve?"
6. User approves → dispatch via `run_actors.py`

Result: 20 posts imported to DuckDB, queryable via `query_dataset.py`

### Example 2: Multi-creator comparison

User says: "Get the last 10 TikTok posts from @creator1 and @creator2"

Actions:
1. Select actor `clockworks/tiktok-scraper` with `profiles: ["creator1", "creator2"]`, `resultsPerPage: 10`
2. Run `estimate_cost.py` — script returns `{"total_usd": 0.15, "source": "cached_registry"}`
3. Present plan with both targets, cost from script output
4. User approves → single job dispatched for both profiles

Result: 20 posts (10 per creator) in DuckDB

## Error Handling

On job failure, present the error adapted to user profile (see `references/error-handling.md`):
- Non-technical: plain language explanation + recommended next step
- Technical: error code, Apify run ID, console link, specific failure reason

Common failures: 403/blocked (try residential proxy), timeout (reduce maxItems), rate limited (wait and retry), auth required (inform user).

Retries go through all four gates again — a retry is a new plan.

## Additional Resources

### Reference Files

- **`references/actor-tables.md`** — Complete actor parameters, optional settings, proxy types, cost breakdowns per platform
- **`references/error-handling.md`** — Platform-specific error patterns and recovery strategies
