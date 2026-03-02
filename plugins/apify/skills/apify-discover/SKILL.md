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
---

# Apify Actor Discovery

Find the right Apify actor for data extraction needs, especially for platforms and data sources beyond the core domains (social media, e-commerce, maps). Activate for platforms not covered by other skills (Reddit, LinkedIn, YouTube, Yelp, etc.), when the user doesn't know if Apify can handle their use case, or when an actor has been deprecated and an alternative is needed.

For lifecycle rules, four-gate enforcement, and script reference, consult `../shared/plugin-rules.md`.

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
3. Rough cost estimate (based on similar actors if exact pricing unknown)
4. Any warnings (community-maintained, infrequent updates, rental required)
5. Alternative actors if available

### Step 5 — Register for Future Use

After a successful run with a newly discovered actor, UPSERT into the `_actor_registry` table in DuckDB with:
- Actor ID, required/optional params, default maxItems
- Proxy type, cost per 100 items (from actual run)
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
