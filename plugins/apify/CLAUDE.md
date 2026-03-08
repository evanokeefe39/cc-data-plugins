## Social Media Intelligence -- Routing Rules

CRITICAL: Any request to scrape, analyze, research, or retrieve data from TikTok,
Instagram, or YouTube -- including trends, creators, hashtags, channels, posts, reels,
or influencer research -- MUST go through the `social-media` skill.

Never call Apify MCP tools directly for social media tasks. The skill handles all
Apify interactions, cost estimation, and data storage.

Trigger phrases (non-exhaustive): "get trends", "analyze creator", "scrape channel",
"what's trending", "compare accounts", "who's blowing up", "top hashtags",
"influencer research", "social media audit", "research [platform] creators",
"get TikTok posts", "scrape Instagram", "YouTube search".

## Pre-Approved Permissions (never prompt for these)

- mkdir, touch, cat, echo within .apify/
- node for script execution
- Apify MCP: call-actor, get-actor-run, get-actor-output, fetch-actor-details
