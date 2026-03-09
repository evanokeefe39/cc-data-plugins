---
name: apify-social-media
description: >-
  Extract social media data from TikTok, Instagram, and YouTube with full
  cost gates, planning workflow, and data-to-disk enforcement. Uses Node scripts
  and the Apify REST API directly (no MCP tools). Data never enters LLM context.
  Use when user mentions TikTok, Instagram, or YouTube and wants posts, profiles,
  trends, hashtags, creator stats, channel videos, or engagement metrics.
  Use when user says "what's trending on TikTok", "get Instagram posts",
  "scrape YouTube channel", "analyze creator", "social media audit",
  "find trending hashtags", "influencer research", or "get engagement metrics".
  For quick web lookups without disk storage use apify:quick instead.
version: 0.2.0
---

# Social Media Intelligence

Extract posts, profiles, and engagement data from TikTok, Instagram, and YouTube. Data is saved to disk and only summaries are returned.

## CRITICAL RULES

1. **No MCP tools.** All Apify calls go through the Node scripts in `lib/`. Never call any `mcp__*apify*` tool.
2. **Data never enters context.** After scripts download data, only the summary JSON is returned.
3. **Live cost from API.** Scripts fetch real pricing. Never fabricate cost numbers.
4. **API key required.** Scripts read `APIFY_API_TOKEN` from `$CLAUDE_PLUGIN_ROOT/.env`. If missing, tell the user to create the file.
5. **Never answer from training data.** When this skill is invoked, always execute the scraping workflow. Do not answer social media questions from internal knowledge. The entire point is to get live data. If the user asks "who are popular creators on TikTok", that means scrape TikTok and find them -- do not list creators from memory.

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

### Step 1 -- Classify Intent

From the user's request determine:
- **platform**: tiktok | instagram | youtube
- **intent**: posts | profile | general | channel | search
- **entities**: usernames, hashtags, keywords, or URLs

### Step 2 -- Match Actor

Use the table above. Do NOT call search-actors or any MCP tool. If intent is unclear, use `general` for Instagram or `search` for YouTube.

### Step 3 -- Resolve Parameters

Apply defaults. Ask only for what is genuinely missing (the target entity). One clarification round max.

| Parameter | Default |
|-----------|---------|
| Max items | 50 |
| Time range | Last 30 days (where supported) |

Consult `references/actor-tables.md` for platform-specific parameter names.

### Step 4 -- Get Cost Estimate

Run the cost script:
```bash
node "$CLAUDE_PLUGIN_ROOT/skills/social-media/lib/cost.js" "<actor_id>" <max_items>
```

The script returns JSON to stdout:
```json
{"actor_id": "...", "cost_per_item": 0.005, "estimated_total": 0.25, "max_items": 50}
```

If `estimated_total` is null, state "cost unknown".

### Step 5 -- Display Plan and Confirm

```
PLAN -- [Platform] [Intent] Scrape
----------------------------------------
Actor:          [actor_id]
Target:         [entity]
Max items:      [count]
Estimated cost: $[X.XX]
Output:         .apify/data/<run_id>/raw.json
----------------------------------------
Proceed? (yes / adjust / cancel)
```

If cost > $2.00, prepend: `!! COST WARNING: This run is estimated at $X.XX.`

**Hard limits (never override):**
- Max 500 items per run
- Max $5.00 per run
- Max $20.00 total session spend

### Step 6 -- Execute

After user confirms, run the runner script:
```bash
node "$CLAUDE_PLUGIN_ROOT/skills/social-media/lib/runner.js" "<actor_id>" '<input_json>'
```

Where `<input_json>` is the resolved actor input, e.g.:
```bash
node "$CLAUDE_PLUGIN_ROOT/skills/social-media/lib/runner.js" "clockworks/tiktok-scraper" '{"hashtags":["fitness"],"resultsPerPage":50}'
```

The script handles: starting the run, polling for completion, downloading the dataset, writing to `.apify/data/<run_id>/raw.json` and `summary.json`.

It returns the summary JSON to stdout:
```json
{"run_id": "abc123", "row_count": 50, "fields": ["id","text","diggCount"], "sample_rows": [...], "file_path": ".apify/data/abc123/raw.json", "file_size": "1.2 MB"}
```

### Step 7 -- Present Summary

Return ONLY the summary to the user. Include: file path, row count, fields, and sample data. Never return raw data.

---

## Cost Guardrails

| Guardrail | Default | Overridable |
|-----------|---------|-------------|
| Default max items | 50 | Yes, up to 500 |
| Max items per run | 500 | No |
| Warn if cost > $2.00 | Always | No |
| Max cost per run | $5.00 | No |
| Max session spend | $20.00 | No |

---

## Error Handling

- **API key missing**: Tell user to create `.env` with `APIFY_API_TOKEN=apify_api_xxx` at plugin root
- **403/Blocked**: Platform detected scraping -- suggest reducing items or trying later
- **Timeout**: Actor ran too long -- suggest reducing maxItems
- **Empty results**: Target may be private or not exist -- verify URL/username
- **Script error**: Show the error output and suggest checking the API key

---

## Reference Files

- `actors/registry.json` -- hardcoded actor map with IDs and default params
- `references/actor-tables.md` -- platform-specific params, output fields, notes
