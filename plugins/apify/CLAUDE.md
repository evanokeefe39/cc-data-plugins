## Apify Plugin — Mandatory Workflow

**NEVER use Apify MCP tools directly.** Always invoke the appropriate skill FIRST:

| User mentions | Invoke skill |
|---------------|-------------|
| Instagram, TikTok, Twitter/X, Facebook | `apify:apify-social-media` |
| Amazon, Shopify, Walmart, products, prices | `apify:apify-ecommerce` |
| Google Maps, business listings, reviews | `apify:apify-maps` |
| Unknown platform, "can Apify do X" | `apify:apify-discover` |
| Account health, storage, cleanup | `apify:apify-maintenance` |

The skills contain actor mappings, cost gates, and workflow rules. Using MCP tools without loading the skill bypasses all safety guardrails.

### Architecture
- DuckDB state backbone with 7 tables: pipeline_runs, apify_jobs, landed_data, _catalog, _diagnostics, _user_config, _actor_registry
- Four-gate enforcement: params, cost, scope, destination
- All artifacts written to `.apify-plugin/` in the project directory (plans in `plans/`, data in `data/`)
