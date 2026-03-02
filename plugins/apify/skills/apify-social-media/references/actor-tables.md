# Social Media Actor Reference Tables

> **Cost data**: Never use hardcoded cost estimates. Always run `estimate_cost.py` to get real pricing from the Apify API or cached registry. The script handles cost lookup, caching, and target multipliers automatically.

## Instagram — `apify/instagram-scraper`

### Required Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `directUrls` | array[string] | Instagram profile URLs, post URLs, or hashtag URLs |

### Optional Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `resultsLimit` | integer | 100 | Maximum items to return (maps to `maxItems`) |
| `resultsType` | string | `"posts"` | One of: `posts`, `comments`, `details` |
| `searchType` | string | — | `hashtag`, `user`, `place` |
| `searchLimit` | integer | 20 | Max search results when using search |
| `addParentData` | boolean | false | Include parent post data with comments |

### Cost Model
- **Proxy**: Residential (required by Instagram's anti-bot measures)
- **Pricing**: Use `estimate_cost.py` — costs are based on real historical runs
- **Typical run time**: 2-5 minutes for 100 posts from a single profile

### Output Fields
Key fields returned per post:
`id`, `type`, `shortCode`, `caption`, `hashtags`, `mentions`, `url`, `commentsCount`, `likesCount`, `videoViewCount`, `timestamp`, `ownerUsername`, `ownerId`, `displayUrl`, `images`, `videoUrl`, `locationName`, `isSponsored`, `isPinned`

### Platform Notes
- Private profiles return no data — no error, just empty results
- Instagram aggressively rate-limits; residential proxies essential
- Stories require separate actor configuration
- Reels are returned as posts with `type: "Video"`

---

## TikTok — `clockworks/tiktok-scraper`

### Required Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `profiles` | array[string] | TikTok usernames (without @) |
| `hashtags` | array[string] | Hashtag search terms (alternative to profiles) |

One of `profiles` or `hashtags` must be provided.

### Optional Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `resultsPerPage` | integer | 100 | Items per profile/hashtag |
| `shouldDownloadVideos` | boolean | false | Download video files |
| `shouldDownloadCovers` | boolean | false | Download cover images |
| `shouldDownloadSubtitles` | boolean | false | Download subtitle files |
| `shouldDownloadSlideshowImages` | boolean | false | Download slideshow images |

### Cost Model
- **Proxy**: Residential (required)
- **Pricing**: Use `estimate_cost.py` — costs are based on real historical runs
- **Typical run time**: 3-8 minutes for 100 posts
- **Cost warning**: Video downloads dramatically increase cost and time

### Output Fields
Key fields returned per post:
`id`, `text`, `createTime`, `authorMeta` (name, fans, following, heart, video, verified), `musicMeta`, `covers`, `webVideoUrl`, `videoUrl`, `diggCount`, `shareCount`, `playCount`, `commentCount`, `hashtags`, `mentions`, `isAd`, `isPinned`

### Platform Notes
- TikTok changes its API frequently — actor may need updates
- Video URLs are temporary; download promptly or they expire
- `diggCount` = likes (TikTok terminology)
- Slideshow posts return multiple images, not video

---

## Twitter/X — `apidojo/tweet-scraper`

### Required Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `searchTerms` | array[string] | Search queries |
| `twitterHandles` | array[string] | Twitter handles (alternative to search) |

One of `searchTerms` or `twitterHandles` must be provided.

### Optional Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `maxItems` | integer | 100 | Maximum tweets to return |
| `sort` | string | `"Top"` | `Top` or `Latest` |
| `tweetLanguage` | string | — | ISO language code filter |
| `onlyVerifiedUsers` | boolean | false | Filter to verified accounts |
| `onlyImage` | boolean | false | Only tweets with images |
| `onlyVideo` | boolean | false | Only tweets with videos |
| `onlyQuote` | boolean | false | Only quote tweets |

### Cost Model
- **Proxy**: Datacenter (sufficient for Twitter API)
- **Pricing**: Use `estimate_cost.py` — costs are based on real historical runs
- **Typical run time**: 1-3 minutes for 100 tweets

### Output Fields
Key fields returned per tweet:
`id`, `url`, `text`, `retweetCount`, `replyCount`, `likeCount`, `quoteCount`, `viewCount`, `bookmarkCount`, `createdAt`, `author` (userName, name, isVerified, followers, following), `isRetweet`, `isQuote`, `isReply`, `media`, `hashtags`, `mentionedUsers`, `place`

### Platform Notes
- Twitter API access may be restricted; actor handles this internally
- Retweets included by default — filter with `isRetweet: false` post-download
- Thread conversations require following `isReply` chains
- Media URLs are persistent (unlike TikTok)

---

## Facebook — `apify/facebook-posts-scraper`

### Required Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `startUrls` | array[object] | Facebook page/group URLs as `{url: "..."}` objects |

### Optional Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `resultsLimit` | integer | 100 | Maximum posts to return |
| `commentsMode` | string | `"NONE"` | `NONE`, `LATEST_10`, `ALL` |
| `reactionsMode` | string | `"NONE"` | `NONE`, `TOP_REACTIONS` |

### Cost Model
- **Proxy**: Residential (recommended)
- **Pricing**: Use `estimate_cost.py` — costs are based on real historical runs
- **Typical run time**: 3-10 minutes depending on content type
- **Cost warning**: Comments mode `ALL` dramatically increases run time and cost

### Output Fields
Key fields returned per post:
`postId`, `postUrl`, `text`, `timestamp`, `likes`, `comments`, `shares`, `views`, `type`, `media`, `authorName`, `authorUrl`, `isLive`, `isPinned`

### Platform Notes
- Facebook heavily restricts scraping — expect some failures
- Group posts may require login (not supported — inform user)
- Pages work better than personal profiles
- Video posts return thumbnail, not video file by default
