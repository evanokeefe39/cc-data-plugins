---
name: apify-social-media
description: >-
  Extracts social media data from TikTok, Instagram, and YouTube via Apify
  actors with cost guardrails, planning gates, and data-to-disk enforcement.
  This skill MUST be used BEFORE any direct Apify MCP tool call. Use when user
  mentions TikTok, Instagram, or YouTube and wants posts, profiles, trends,
  hashtags, creator stats, channel videos, or engagement metrics. Use when user
  says "what's trending on TikTok", "get Instagram posts", "scrape YouTube
  channel", "analyze creator", "social media audit", "find trending hashtags",
  "influencer research", "who's blowing up", or "get engagement metrics".
  Also use when the goal is analysis or visualization — extraction comes first.
  Do NOT call Apify MCP tools directly — this skill contains the required workflow.
version: 0.1.0
compatibility: "Requires Apify MCP server (mcp.apify.com)"
metadata:
  author: cc-data-plugins
  mcp-server: apify
---

# Social Media Intelligence

Extract posts, profiles, and engagement data from TikTok, Instagram, and YouTube using Apify actors.

## CRITICAL: No Actor Search

Do NOT call the Apify MCP "search-actors" tool. All actors are pre-mapped in `actors/registry.json`. Go directly to actor selection and the planning gate workflow below.

## CRITICAL: Data Never Enters LLM Context

After fetching actor output, ALWAYS write the full response to disk first, then return only a summary. Never return raw data arrays inline. This is a hard rule with no exceptions.

## CRITICAL: Live Cost From API

Never use hardcoded cost numbers. Always call `mcp__apify__fetch-actor-details` to get real pricing before presenting a cost estimate. If the API returns no pricing info, state "cost unknown". Never fabricate a number.

---

## Workflow

Follow these steps in order for every social media data request. Do not skip steps.

### Step 1 -- Classify Intent

From the user's request, determine:
- **platform**: `tiktok` | `instagram` | `youtube`
- **intent**: `posts` | `profile` | `general` | `channel` | `search`
- **entities**: usernames, hashtags, keywords, or URLs already in the prompt

### Step 2 -- Look Up Actor

Match `platform` + `intent` to the actor table below. Do NOT read any files -- the mapping is right here. Default max items is 50 for all actors.

Actor mapping:

| Platform | Intent | Actor ID |
|----------|--------|----------|
| TikTok | posts | `clockworks/tiktok-scraper` |
| TikTok | profile | `clockworks/tiktok-profile-scraper` |
| Instagram | posts | `apify/instagram-post-scraper` |
| Instagram | profile | `apify/instagram-profile-scraper` |
| Instagram | general | `apify/instagram-scraper` |
| YouTube | channel | `streamers/youtube-channel-scraper` |
| YouTube | search | `streamers/youtube-scraper` |

If the intent doesn't map cleanly, use `general` for Instagram or `search` for YouTube.

### Step 3 -- Resolve Parameters

Apply defaults. Ask only for what is genuinely missing (the target entity). Maximum one clarification round before proceeding with defaults.

| Parameter | Default |
|-----------|---------|
| Max items | 50 |
| Time range | Last 30 days (where supported) |
| Proxy | Automatic (actor default) |

Consult `references/actor-tables.md` for platform-specific parameter names and output fields.

### Step 4 -- Fetch Real Cost From API

Call `mcp__apify__fetch-actor-details` with the actor ID from Step 2. Extract the `pricingInfo` field from the response.

Calculate the estimated cost:
- If pricing is per-result: `cost = price_per_result * max_items`
- If pricing is per compute unit: use the CU rate and estimated run duration
- If no pricing info returned: state "cost unknown -- check Apify console for pricing"

**Cost caching**: After fetching, write the pricing data to `.apify/cost-cache/<actor_slug>.json` with a timestamp. On subsequent calls within the same session, read from cache if less than 24 hours old instead of calling the API again. Create the directory if it doesn't exist:

```bash
mkdir -p .apify/cost-cache
```

### Step 5 -- Display Plan and Wait for Confirmation

Present a plan block to the user. The cost MUST come from Step 4.

```
PLAN -- [Platform] [Intent] Scrape
----------------------------------------
Actor:          [actor_id]
Target:         [entity]
Max items:      [count]
Estimated cost: $[X.XX] ([count] x $[per_item]/item)
Output:         .apify/data/<run_id>/raw.json
----------------------------------------
Proceed? (yes / adjust / cancel)
```

If estimated cost > $2.00, prepend a warning:

```
!! COST WARNING: This run is estimated at $X.XX.
Re-confirm to proceed.
```

**Hard limits (never override):**
- Max 500 items per run
- Max $5.00 per run
- Max $20.00 total session spend

If any limit would be exceeded, refuse and explain.

### Step 6 -- Execute

After explicit user confirmation:

1. Call `mcp__apify__call-actor` with the actor ID and resolved input parameters
2. Poll with `mcp__apify__get-actor-run` using the returned run ID

Polling backoff schedule:
- 0-5 minutes: every 30 seconds
- 5-20 minutes: every 60 seconds
- 20+ minutes: every 300 seconds

### Step 7 -- Download and Save to Disk

On run success:

1. Call `mcp__apify__get-actor-output` to fetch the dataset
2. Create the output directory:
   ```bash
   mkdir -p .apify/data/<run_id>
   ```
3. **Immediately write the full response to `.apify/data/<run_id>/raw.json` via Bash.** Do NOT hold the raw data in context. Pipe it directly to file.
4. Generate a summary object from the data:
   - `row_count`: number of items
   - `fields`: field names from the first row
   - `sample_rows`: first 3 rows only
   - `file_path`: path to raw.json
   - `file_size`: size of raw.json
5. Write the summary to `.apify/data/<run_id>/summary.json`
6. Return ONLY the summary to the user -- file path, row count, fields, and sample

### Step 8 -- Gitignore

On first use, check if `.apify/` is in `.gitignore`. If not, append it:

```bash
grep -q '.apify/' .gitignore 2>/dev/null || echo '.apify/' >> .gitignore
```

---

## Cost Guardrails

| Guardrail | Default | Overridable |
|-----------|---------|-------------|
| Default max items | 50 | Yes -- user can specify up to 500 |
| Max items per run | 500 | No |
| Warn if cost > $2.00 | Always | No |
| Max cost per run | $5.00 | No |
| Max session spend | $20.00 | No -- hard stop |

If the session total would be exceeded: refuse, explain the limit, and suggest continuing in a new session.

---

## Data Handling Rules

- Data NEVER passes through LLM context -- always write to disk first
- After `get-actor-output`, immediately write to `.apify/data/<run_id>/raw.json`
- Generate summary: `{ row_count, fields, sample_rows (3), file_path, file_size }`
- Present only the summary to the user
- The raw data file is referenced by path for any follow-up analysis

---

## Three-Tier Boundary System

**Always (no confirmation needed):**
- Create directories under `.apify/`
- Save plan to `.apify/plans/` before confirmation
- Write data files to `.apify/data/`
- Add `.apify/` to `.gitignore`
- Call `fetch-actor-details` for pricing info
- Return summary only after download

**Ask first (require confirmation):**
- Any Apify run (always, via the plan gate)
- Runs estimated over $2.00 (additional warning)
- Overriding max items above 500
- Overriding max cost per run above $5.00

**Never:**
- Call Apify MCP tools without going through the planning gate
- Return full raw.json content inline to the LLM
- Exceed $20.00 total session spend -- hard stop, no override
- Write files outside `.apify/` in the project directory
- Use `search-actors` to find actors -- all actors are hardcoded
- Guess or fabricate cost numbers

---

## Examples

### Example 1: Get trending TikTok posts

User says: "What's trending on TikTok for #fitness?"

1. Classify: platform=tiktok, intent=posts, entity=#fitness
2. Actor: `clockworks/tiktok-scraper` with `hashtags: ["fitness"]`, max 50
3. Call `fetch-actor-details` for `clockworks/tiktok-scraper` -- get real pricing
4. Display plan with real cost from API
5. User confirms -> call `call-actor`
6. Poll with `get-actor-run` until SUCCEEDED
7. Fetch output, write to `.apify/data/<run_id>/raw.json`
8. Return summary: "50 posts saved to .apify/data/abc123/raw.json. Fields: id, text, diggCount, shareCount, playCount, commentCount, createTime, authorMeta..."

### Example 2: Instagram creator profile

User says: "Get me @natgeo's Instagram profile info"

1. Classify: platform=instagram, intent=profile, entity=natgeo
2. Actor: `apify/instagram-profile-scraper` with `usernames: ["natgeo"]`, max 1
3. Call `fetch-actor-details` for `apify/instagram-profile-scraper` -- get real pricing
4. Display plan with real cost
5. User confirms -> execute, download, return summary

### Example 3: YouTube channel videos

User says: "Get the latest 20 videos from MKBHD's YouTube channel"

1. Classify: platform=youtube, intent=channel, entity=MKBHD
2. Actor: `streamers/youtube-channel-scraper` with `startUrls: [{url: "https://www.youtube.com/@mkbhd"}]`, max 20
3. Call `fetch-actor-details` for `streamers/youtube-channel-scraper` -- get real pricing
4. Display plan with real cost
5. User confirms -> execute, download, return summary

---

## Error Handling

On job failure, present the error clearly:
- **403/Blocked**: Platform detected scraping -- suggest reducing items or trying later
- **Timeout**: Actor ran too long -- suggest reducing maxItems
- **Rate limited**: Too many requests -- suggest waiting and retrying
- **Empty results**: Target may be private or not exist -- verify the URL/username

Retries go through the full planning gate again -- a retry is a new plan.

---

## Reference Files

- `actors/registry.json` -- hardcoded actor map with IDs and default params
- `references/actor-tables.md` -- platform-specific params, output fields, notes
