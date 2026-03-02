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
---

# Apify Social Media Extraction

Extract posts, profiles, and engagement data from Instagram, TikTok, Twitter/X, and Facebook using Apify actors.

For lifecycle rules (INIT → PLAN → EXECUTE → REPLAN), four-gate enforcement, data handling rules, and script reference, consult `../shared/plugin-rules.md`.

## Planning Flow

1. Check existing data first — run `uv run $CLAUDE_PLUGIN_ROOTscripts/query_dataset.py sql "SELECT * FROM landed_data"` to check for relevant data already downloaded. If local data answers the question, query it directly — no scrape needed
2. Identify the target platform and content type from the user's request
3. Select the correct actor from the actor table (see `references/actor-tables.md`)
4. Resolve all required parameters — ask the user for any missing inputs (profile URLs, hashtags, search terms)
5. Set `maxItems` — never leave unbounded. Default to 100 unless the user specifies otherwise
6. Check `_catalog` for known output fields for this actor. If known, summarize available fields so the user can make informed scope decisions
7. Estimate cost using skill-embedded rough estimates (Plan Mode) or `estimate_cost.py` (Normal Mode)
8. Present the full execution plan for four-gate approval

## Social Media Specific Rules

### Pinned Posts

Exclude pinned posts by default — they skew engagement metrics and recency filters. Include only when the user explicitly requests them.

### Default Media Behavior

Default to downloading media locally rather than storing in Apify KV. KV storage incurs GB-hour costs. On first media download, ask the user for their preference and store it in the `_user_config` table in DuckDB.

## Actor Quick Reference

| Platform | Actor ID | Required Params | Credits/100 |
|----------|----------|-----------------|-------------|
| Instagram | `apify/instagram-scraper` | `directUrls` | ~1.5 |
| TikTok | `clockworks/tiktok-scraper` | `profiles` or `hashtags` | ~2.0 |
| Twitter/X | `apidojo/tweet-scraper` | `searchTerms` or `twitterHandles` | ~1.0 |
| Facebook | `apify/facebook-posts-scraper` | `startUrls` | ~2.0 |

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
