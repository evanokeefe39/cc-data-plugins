# E-Commerce Actor Reference Tables

> **Cost data**: Never use hardcoded cost estimates. Always run `estimate_cost.py` to get real pricing from the Apify API or cached registry. The script handles cost lookup, caching, and target multipliers automatically.

## Amazon — `junglee/amazon-crawler`

### Required Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `keyword` | string | Search keyword on Amazon |
| `asins` | array[string] | Specific product ASINs (alternative to keyword) |

One of `keyword` or `asins` must be provided.

### Optional Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `maxItems` | integer | 100 | Maximum products to return |
| `domain` | string | `"amazon.com"` | Amazon marketplace domain |
| `includeReviews` | boolean | false | Include product reviews |
| `includeDescription` | boolean | true | Include product description |
| `proxy` | object | — | Proxy configuration |

### Cost Model
- **Proxy**: Residential (required for Amazon)
- **Pricing**: Use `estimate_cost.py` — costs are based on real historical runs
- **Rental**: May require monthly subscription ($10-$150/month) — CHECK FIRST
- **Typical run time**: 5-15 minutes for 100 products
- **Cost warning**: Amazon is the most expensive platform. Reviews dramatically increase run time

### Output Fields
`title`, `asin`, `url`, `price`, `listPrice`, `currency`, `stars`, `reviewsCount`, `isPrime`, `isSponsored`, `brand`, `seller`, `categories`, `images`, `description`, `features`, `availability`, `deliveryInfo`

### Platform Notes
- Amazon aggressively blocks scrapers — expect occasional failures
- Price may be null for out-of-stock items or marketplace-only listings
- Sponsored products mixed into search results — filter via `isSponsored`
- Different Amazon domains (.co.uk, .de, .co.jp) return different products and currencies

---

## Walmart — `piotrv1001/walmart-listings-scraper`

### Required Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `searchTerms` | array[string] | Product search queries |

### Optional Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `maxItems` | integer | 100 | Maximum products to return |
| `sort` | string | `"best_match"` | Sort order |

### Cost Model
- **Proxy**: Residential (recommended)
- **Pricing**: Use `estimate_cost.py` — costs are based on real historical runs
- **No rental required**
- **Typical run time**: 3-8 minutes for 100 products

### Output Fields
`name`, `url`, `price`, `wasPrice`, `currency`, `rating`, `reviewCount`, `seller`, `brand`, `categories`, `images`, `availability`, `fulfillment`

---

## Shopify — `autofacts/shopify`

### Required Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `startUrls` | array[object] | Shopify store URLs as `{url: "..."}` |

### Optional Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `maxItems` | integer | 100 | Maximum products to return |
| `includeVariants` | boolean | true | Include product variants |

### Cost Model
- **Proxy**: Datacenter (Shopify stores don't typically block)
- **Pricing**: Use `estimate_cost.py` — costs are based on real historical runs
- **No rental required**
- **Typical run time**: 2-5 minutes for 100 products

### Output Fields
`title`, `handle`, `url`, `price`, `compareAtPrice`, `currency`, `vendor`, `productType`, `tags`, `images`, `variants` (array of size/color/price), `description`, `available`, `createdAt`, `updatedAt`

### Platform Notes
- Works on any Shopify-powered store
- Variants expand data significantly — one product with 10 variants = 10 rows
- Some stores may have custom anti-bot measures on top of Shopify

---

## General E-Commerce — `apify/e-commerce-scraping-tool`

### Required Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `startUrls` | array[object] | Any e-commerce site URLs |

### Cost Model
- **Proxy**: Residential (recommended for unknown sites)
- **Pricing**: Use `estimate_cost.py` — costs are based on real historical runs
- **Typical run time**: 5-15 minutes (varies significantly)
- **Use as fallback only** — platform-specific actors are more reliable

### Output Fields
Fields vary by site. Common: `name`, `price`, `url`, `image`, `description`, `availability`

### Platform Notes
- Generic scraper — less reliable than platform-specific actors
- Output schema varies per site — expect schema discovery to find new fields
- Recommend using platform-specific actors first, falling back to this only when no specific actor exists
