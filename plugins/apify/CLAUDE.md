## Social Media Intelligence -- Mandatory Routing

BEFORE using ANY Apify MCP tool (search-actors, call-actor, fetch-actor-details, get-actor-run, get-actor-output, or any other mcp__plugin_apify_apify__* tool), you MUST first invoke the skill `apify:social-media` using the Skill tool.

This applies to ALL requests mentioning TikTok, Instagram, or YouTube -- including trends, creators, hashtags, channels, posts, reels, influencer research, social media audits, or any social media data task.

DO NOT call any Apify MCP tool directly. DO NOT search for actors. The skill contains hardcoded actor mappings and a mandatory planning gate. Load the skill FIRST, then follow its instructions.

## Pre-Approved Permissions (never prompt for these)

- mkdir, touch, cat, echo within .apify/
- node for script execution
- Apify MCP: call-actor, get-actor-run, get-actor-output, fetch-actor-details
