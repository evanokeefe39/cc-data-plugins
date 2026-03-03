---
name: apify-ecommerce
description: >-
  This skill should be used when the user asks to "scrape Amazon", "get product data",
  "extract prices", "scrape Shopify store", "get product reviews", "scrape product pages",
  "scrape Walmart", "extract e-commerce data", "get product listings", "crawl e-commerce site",
  "extract product catalog", "ASIN lookup", or mentions Amazon, Shopify, Walmart,
  or product/price/review extraction in the context of data collection.
  Do NOT use for product analysis, price optimization, comparison, or visualization — only for extracting raw product data via Apify.
version: 0.1.0
---

# Apify E-Commerce Extraction

Extract product listings, prices, reviews, and catalog data from Amazon, Shopify, Walmart, and general e-commerce sites using Apify actors.

For lifecycle rules, four-gate enforcement, data handling rules, and script reference, consult `../shared/plugin-rules.md`.

## Planning Flow

1. Check existing data first — run `uv run $CLAUDE_PLUGIN_ROOTscripts/query_dataset.py sql "SELECT * FROM landed_data"` before proposing a new scrape
2. Identify the target platform and data type (products, reviews, prices, search results)
3. Select the correct actor from the actor table (see `references/actor-tables.md`)
4. **Check for actor rental requirements** — some e-commerce actors (e.g., `junglee/amazon-crawler`) require a monthly subscription. Warn the user before proceeding
5. Resolve all required parameters — product URLs, search queries, category pages
6. Set `maxItems` — default to 100. E-commerce scrapes can be large; enforce bounds
7. **Estimate cost** — STOP and run `estimate_cost.py --plan <plan.json>` before presenting costs to the user. Never write cost numbers (USD or otherwise) without script output. If the script returns `cost_unknown`, tell the user no cost data is available yet
8. Present the full execution plan for four-gate approval — cost numbers in the plan MUST come from step 7's script output

### Actor Selection

| Platform | Actor ID | Required Params | Notes |
|----------|----------|-----------------|-------|
| Amazon | `junglee/amazon-crawler` | `keyword` or `asins` | May require rental ($10-150/mo) |
| Walmart | `piotrv1001/walmart-listings-scraper` | `searchTerms` | |
| Shopify | `autofacts/shopify` | `startUrls` | Works on any Shopify store |
| General | `apify/e-commerce-scraping-tool` | `startUrls` | Fallback only — less reliable |

**Costs**: You MUST run `estimate_cost.py --plan <file>` to get real USD pricing. Never write cost numbers without running the script first. Never use the term "credits".

For complete parameters, cost models, and platform notes, consult `references/actor-tables.md`.

### Rental Actor Warning

Before using any actor that requires rental:
1. Check if the user already has the rental active (query Apify API)
2. If not, inform the user of the monthly cost and ask for confirmation
3. Never dispatch a rental actor without explicit user awareness of the recurring charge

### E-Commerce Specific Considerations

- **Price data is time-sensitive** — note the extraction timestamp prominently
- **Product variants** (size, color) may appear as separate items or nested — depends on actor
- **Review scraping** can be very large — enforce `maxItems` strictly
- **Amazon search results** return sponsored products mixed in — flag `isSponsored` field
- **Currency** — prices return in the marketplace's local currency. Note the currency in results

### Post-Download Validation

After download and import (see `../shared/plugin-rules.md` for execution steps):
- Check for empty price fields, missing images, duplicate ASINs
- Flag `isSponsored` products in search results
- Note currency in results (marketplace-local)

## Examples

### Example 1: Search Amazon for products

User says: "Find the top 50 wireless earbuds on Amazon"

Actions:
1. Check existing data: `uv run scripts/query_dataset.py sql "SELECT * FROM landed_data WHERE source LIKE '%amazon%'"`
2. No local data — select `junglee/amazon-crawler` with `keyword: "wireless earbuds"`, `maxItems: 50`
3. Check for rental requirement via Apify API — actor requires rental, warn user
4. User confirms rental is active
5. Write plan JSON, run `uv run scripts/estimate_cost.py --plan /tmp/plan.json` — returns `{"total_usd": 0.25, "source": "live_api"}`
6. Present plan: "50 Amazon results for 'wireless earbuds', ~$0.25 USD, metadata only. Approve?"
7. User approves → dispatch

Result: 50 product listings in DuckDB with prices, ratings, ASINs

### Example 2: Scrape a Shopify store

User says: "Get all products from example-store.myshopify.com"

Actions:
1. Select `autofacts/shopify` with `startUrls: ["https://example-store.myshopify.com"]`, `maxItems: 100`
2. Run `estimate_cost.py` — returns `{"total_usd": 0.12, "source": "cached_registry"}`
3. Present plan with cost from script
4. Dispatch after approval

Result: Product catalog imported, queryable by price/category

## Error Handling

Common e-commerce failures:
- **Actor rental not active**: Inform user, provide subscription link
- **CAPTCHA / blocked**: Amazon and Walmart have strong anti-bot. Suggest reducing scope or trying at off-peak hours
- **Product not found**: ASIN/URL may be discontinued. Inform user, skip item
- **Price = 0 or null**: Product may be out of stock or price hidden. Flag in validation

Retries go through all four gates again.

## Additional Resources

### Reference Files

- **`references/actor-tables.md`** — Complete actor parameters, cost breakdowns, output fields per platform
