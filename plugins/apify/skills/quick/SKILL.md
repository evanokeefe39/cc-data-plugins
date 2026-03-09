---
name: apify-quick
description: >-
  Quick social media data lookups using Apify MCP tools directly. Use for fast
  TikTok, Instagram, or YouTube queries when you don't need data saved to disk.
  Best for mobile or web use. For full data-to-disk workflows use apify:social-media instead.
  Use when user says "quick scrape", "check trending", "look up creator",
  "get posts from", "what's trending on TikTok", "Instagram profile for",
  "YouTube videos from", or any social media data request on claude.ai web.
version: 0.1.0
---

# Quick Social Media Lookup

Fast social media data extraction using Apify MCP tools directly. Data stays in context (no disk writes).

## Actor Mapping

| Platform | Intent | Actor ID |
|----------|--------|----------|
| TikTok | posts | `clockworks/tiktok-scraper` |
| TikTok | profile | `clockworks/tiktok-profile-scraper` |
| Instagram | posts | `apify/instagram-post-scraper` |
| Instagram | profile | `apify/instagram-profile-scraper` |
| Instagram | general | `apify/instagram-scraper` |
| YouTube | channel | `streamers/youtube-channel-scraper` |
| YouTube | search | `streamers/youtube-scraper` |

## Workflow

### Step 1 -- Classify
From the user's request determine: platform, intent (posts/profile/general/channel/search), and entities (usernames, hashtags, keywords, URLs).

### Step 2 -- Match Actor
Use the table above. Do NOT call search-actors. If intent is unclear, use `general` for Instagram or `search` for YouTube.

### Step 3 -- Get Cost
Call `fetch-actor-details` with the actor ID. Extract pricing info. If no pricing returned, say "cost unknown".

### Step 4 -- Confirm
Show the user:
```
Actor:     [actor_id]
Target:    [entity]
Max items: [count, default 50, max 200]
Est. cost: $[X.XX]
Proceed? (yes / adjust / cancel)
```
If cost > $2.00, warn before confirming. Never exceed $5.00/run or $20.00/session.

### Step 5 -- Run
After confirmation, call `call-actor` with the actor ID and parameters. Poll with `get-actor-run` until complete.

### Step 6 -- Results
On success, call `get-actor-output`. Summarise the results for the user: count, key fields, highlights. Data will be in context (this is the web version -- no disk available).

## Guardrails
- Default 50 items, max 200 per run
- Always confirm before running
- Warn if cost > $2.00
- Hard limit $5.00/run, $20.00/session
- Never call search-actors
- Never fabricate cost numbers
