---
name: apify-maps
description: >-
  This skill should be used when the user asks to "scrape Google Maps", "get business listings",
  "extract place reviews", "find businesses near", "get restaurant data", "scrape local businesses",
  "extract Google Places data", "get reviews for a business", "scrape business contact info",
  "extract ratings and reviews", "find coffee shops in [city]",
  or mentions Google Maps, business listings, place reviews, or local business data extraction.
  Do NOT use for mapping, visualization, or route planning — only for extracting business and review data via Apify.
version: 0.1.0
---

# Apify Maps & Places Extraction

Extract business listings, reviews, and place details from Google Maps using Apify actors. Two actors cover this domain: one for business discovery/listings and one for review extraction.

For lifecycle rules, four-gate enforcement, data handling rules, and script reference, consult `../shared/plugin-rules.md`.

## Planning Flow

1. Determine what the user needs: business listings, reviews, or both
2. Select the correct actor:
   - **Business listings/discovery** → `compass/crawler-google-places`
   - **Reviews only** (for known places) → `compass/Google-Maps-Reviews-Scraper`
3. Resolve required parameters — search queries, location, place URLs
4. Set item limits — `maxCrawledPlacesPerSearch` (default 100) for listings, `maxReviews` (default 200) for reviews
5. Estimate cost and present four-gate execution plan

### Actor Selection

| Use Case | Actor ID | Required Params | Credits/100 |
|----------|----------|-----------------|-------------|
| Business listings | `compass/crawler-google-places` | `searchStringsArray` + `locationQuery` | ~2.0 |
| Reviews | `compass/Google-Maps-Reviews-Scraper` | `startUrls` | ~1.5 |

For complete parameters consult `references/actor-tables.md`.

### Two-Step Pattern: Listings Then Reviews

A common workflow:
1. First scrape: extract business listings for a category/location
2. User reviews results, selects businesses of interest
3. Second scrape: extract reviews for selected businesses only

Present this as an option when the user asks for "businesses with reviews" — it avoids downloading reviews for irrelevant businesses and saves credits.

### Location Handling

- Google Maps results are location-dependent. Always confirm the target location/region
- `locationQuery` accepts city names, addresses, coordinates, or "near me" style queries
- For multi-location scrapes, plan sequential runs (one per location) to keep costs predictable

### Post-Download Validation

After download and import (see `../shared/plugin-rules.md` for execution steps):
- Check for empty address fields, missing coordinates, duplicate place IDs
- For reviews: check for empty review text, verify rating distribution

## Error Handling

Common failures:
- **No results for location**: Query may be too specific. Broaden the search area or simplify terms
- **Partial results**: Google rate-limits Maps data. Accept partial, offer to retry for remainder
- **Stale place URLs**: Business may have closed or moved. Flag in validation results

## Additional Resources

### Reference Files

- **`references/actor-tables.md`** — Complete actor parameters, output fields, cost breakdowns
