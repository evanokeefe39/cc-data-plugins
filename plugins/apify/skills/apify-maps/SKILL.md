---
name: apify-maps
description: >-
  This skill should be used when the user mentions Google Maps, local businesses, places,
  or reviews and needs data from those platforms — whether the goal is extraction, analysis,
  competitive research, or location scouting. Trigger words include "scrape Google Maps",
  "get business listings", "extract place reviews", "find businesses near",
  "get restaurant data", "scrape local businesses", "extract Google Places data",
  "get reviews for a business", "scrape business contact info", "extract ratings and reviews",
  "find coffee shops in [city]", "compare restaurants", "analyze reviews".
  Use this skill even when the user's end goal is analysis or visualization — data must be
  extracted first, and this skill handles that extraction step.
version: 0.1.0
compatibility: "Requires Python 3.11+, uv, and Apify MCP server (@apify/actors-mcp-server)"
metadata:
  author: cc-data-plugins
  mcp-server: apify
---

# Apify Maps & Places Extraction

Extract business listings, reviews, and place details from Google Maps using Apify actors. Two actors cover this domain: one for business discovery/listings and one for review extraction.

## CRITICAL: No Actor Search — Use Hardcoded Actors

Do NOT call the Apify MCP "Search Actors" tool. All maps actors are pre-mapped in the Actor Selection table below. Go directly to actor selection → four-gate flow. The MCP search exists only for the `apify-discover` skill.

## CRITICAL: Packaged Scripts Only

NEVER write inline Python, ad-hoc DuckDB queries, or custom Bash. ALWAYS use `uv run "$CLAUDE_PLUGIN_ROOT/scripts/<script>"`. These are pre-authorized — inline code triggers permission prompts and breaks the flow.

## Four Gates (mandatory before any dispatch)

All four must pass. Enforced by skill instructions (soft), PreToolUse hook (hard), and script validation (hard).

1. **Params Complete** — All required params resolved, item limit set (`maxCrawledPlacesPerSearch`/`maxReviews`/etc.)
2. **Cost Approved** — `estimate_cost.py` run, estimate presented, user explicitly confirmed
3. **Scope Decided** — `metadata_only`, `with_media`, or `with_transcripts`
4. **Destination Set** — `local_duckdb`, `local_files`, `remote`, or `decide_later`

### Plan JSON format

Write to a `.json` file, pass via `--plan <file>`:
```json
{
  "session_id": "abc-123",
  "user_request": "Find coffee shops in Austin TX",
  "jobs": [
    {
      "actor_id": "compass/crawler-google-places",
      "input": {
        "searchStringsArray": ["coffee shops"],
        "locationQuery": "Austin, TX",
        "maxCrawledPlacesPerSearch": 100
      }
    }
  ],
  "cost_approval": {
    "approved": true,
    "estimated_cost": 0.35,
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

**Do NOT use the Apify MCP "Search Actors" tool.** All maps actors are already mapped below — go directly to actor selection and the four-gate flow. The MCP search is only for the `apify-discover` skill when handling unknown platforms.

1. Determine what the user needs: business listings, reviews, or both
2. Select the correct actor:
   - **Business listings/discovery** → `compass/crawler-google-places`
   - **Reviews only** (for known places) → `compass/Google-Maps-Reviews-Scraper`
3. Resolve required parameters — search queries, location, place URLs
4. Set item limits — `maxCrawledPlacesPerSearch` (default 100) for listings, `maxReviews` (default 200) for reviews
5. **Estimate cost** — STOP and run `estimate_cost.py --plan <plan.json>` before presenting costs to the user. Never write cost numbers (USD or otherwise) without script output. If the script returns `cost_unknown`, tell the user no cost data is available yet
6. Present the full execution plan for four-gate approval — cost numbers in the plan MUST come from step 5's script output

### Actor Selection

| Use Case | Actor ID | Required Params |
|----------|----------|-----------------|
| Business listings | `compass/crawler-google-places` | `searchStringsArray` + `locationQuery` |
| Reviews | `compass/Google-Maps-Reviews-Scraper` | `startUrls` |

**Costs**: You MUST run `estimate_cost.py --plan <file>` to get real USD pricing. Never write cost numbers without running the script first. Never use the term "credits".

For complete parameters consult `references/actor-tables.md`.

### Two-Step Pattern: Listings Then Reviews

A common workflow:
1. First scrape: extract business listings for a category/location
2. User reviews results, selects businesses of interest
3. Second scrape: extract reviews for selected businesses only

Present this as an option when the user asks for "businesses with reviews" — it avoids downloading reviews for irrelevant businesses and saves money.

### Location Handling

- Google Maps results are location-dependent. Always confirm the target location/region
- `locationQuery` accepts city names, addresses, coordinates, or "near me" style queries
- For multi-location scrapes, plan sequential runs (one per location) to keep costs predictable

### Post-Download Validation

After download and import (see `../shared/plugin-rules.md` for execution steps):
- Check for empty address fields, missing coordinates, duplicate place IDs
- For reviews: check for empty review text, verify rating distribution

## Examples

### Example 1: Find coffee shops in a city

User says: "Find coffee shops in Austin, TX"

Actions:
1. Select `compass/crawler-google-places` with `searchStringsArray: ["coffee shops"]`, `locationQuery: "Austin, TX"`, `maxCrawledPlacesPerSearch: 100`
2. Write plan JSON, run `uv run "$CLAUDE_PLUGIN_ROOT/scripts/estimate_cost.py" --plan .apify-plugin/plans/plan.json` — returns `{"total_usd": 0.35, "source": "live_api"}`
3. Present plan: "100 coffee shops in Austin, ~$0.35 USD, metadata only. Approve?"
4. User approves → dispatch

Result: 100 business listings in DuckDB with names, addresses, ratings, phone numbers

### Example 2: Two-step listings then reviews

User says: "Find Italian restaurants in Chicago with reviews"

Actions:
1. First scrape: `compass/crawler-google-places` for listings (maxCrawledPlacesPerSearch: 50)
2. Run `estimate_cost.py` for first job, present plan, dispatch after approval
3. Import results, present top restaurants to user
4. User selects 5 restaurants → second scrape: `compass/Google-Maps-Reviews-Scraper` with those 5 place URLs
5. Run `estimate_cost.py` for second job, present plan, dispatch after approval

Result: Two DuckDB tables — listings + reviews for selected restaurants

## Error Handling

Common failures:
- **No results for location**: Query may be too specific. Broaden the search area or simplify terms
- **Partial results**: Google rate-limits Maps data. Accept partial, offer to retry for remainder
- **Stale place URLs**: Business may have closed or moved. Flag in validation results

## Additional Resources

### Reference Files

- **`references/actor-tables.md`** — Complete actor parameters, output fields, cost breakdowns
