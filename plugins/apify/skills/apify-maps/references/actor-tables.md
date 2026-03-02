# Maps & Places Actor Reference Tables

> **Cost data**: Never use hardcoded cost estimates. Always run `estimate_cost.py` to get real pricing from the Apify API or cached registry. The script handles cost lookup, caching, and target multipliers automatically.

## Google Places Listings — `compass/crawler-google-places`

### Required Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `searchStringsArray` | array[string] | Search queries (e.g., "pizza", "dentist") |
| `locationQuery` | string | Location to search in (e.g., "New York, NY") |

### Optional Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `maxCrawledPlacesPerSearch` | integer | 100 | Max places per search query |
| `language` | string | `"en"` | Language for results |
| `maxReviews` | integer | 0 | Reviews per place (0 = none) |
| `maxImages` | integer | 0 | Images per place (0 = none) |
| `includeWebResults` | boolean | false | Include web search results |
| `zoom` | integer | — | Map zoom level (affects search radius) |

### Cost Model
- **Proxy**: Datacenter (sufficient for Google Maps)
- **Pricing**: Use `estimate_cost.py` — costs are based on real historical runs
- **Typical run time**: 3-10 minutes for 100 listings

### Output Fields
`title`, `categoryName`, `address`, `street`, `city`, `state`, `postalCode`, `countryCode`, `phone`, `website`, `url`, `totalScore`, `reviewsCount`, `latitude`, `longitude`, `placeId`, `categories`, `openingHours`, `priceLevel`, `temporarilyClosed`, `permanentlyClosed`, `imageUrls`, `additionalInfo`

### Platform Notes
- Results are heavily influenced by location and zoom level
- `maxCrawledPlacesPerSearch` applies per search term — 3 terms x 100 = up to 300 results
- Including reviews in the same run increases cost significantly. Consider the two-step pattern instead
- `totalScore` is the star rating (1-5 scale)

---

## Google Maps Reviews — `compass/Google-Maps-Reviews-Scraper`

### Required Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `startUrls` | array[object] | Google Maps place URLs as `{url: "..."}` |

### Optional Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `maxReviews` | integer | 200 | Maximum reviews per place |
| `reviewsSort` | string | `"newest"` | `newest`, `mostRelevant`, `highestRating`, `lowestRating` |
| `language` | string | `"en"` | Review language filter |
| `reviewsStartDate` | string | — | ISO date to filter reviews after |

### Cost Model
- **Proxy**: Datacenter
- **Pricing**: Use `estimate_cost.py` — costs are based on real historical runs
- **Typical run time**: 2-5 minutes per place

### Output Fields
`name`, `text`, `publishAt`, `publishedAtDate`, `likesCount`, `reviewId`, `reviewUrl`, `reviewerId`, `reviewerName`, `reviewerNumberOfReviews`, `isLocalGuide`, `stars`, `responseFromOwnerDate`, `responseFromOwnerText`, `placeUrl`, `placeTitle`

### Platform Notes
- Sort by `newest` for recent sentiment analysis
- `reviewsStartDate` is useful for incremental scraping (only get reviews since last run)
- Owner responses included when available — useful for reputation analysis
- Some reviews may be in other languages despite language filter (Google limitation)
