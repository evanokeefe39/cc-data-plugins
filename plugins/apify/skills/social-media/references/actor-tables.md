# Social Media Actor Reference Tables

> Cost data: Never use hardcoded cost estimates. Always call `mcp__apify__fetch-actor-details` to get real pricing from the Apify API before presenting cost to the user. If no pricing info is returned, state "cost unknown".

## TikTok

### Posts -- `clockworks/tiktok-scraper`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `profiles` | array[string] | One of | -- | TikTok usernames (without @) |
| `hashtags` | array[string] | One of | -- | Hashtag search terms |
| `searchQueries` | array[string] | One of | -- | Search keywords |
| `postURLs` | array[string] | One of | -- | Direct post URLs |
| `resultsPerPage` | integer | No | 50 | Items per profile/hashtag |
| `shouldDownloadVideos` | boolean | No | false | Download video files |
| `shouldDownloadCovers` | boolean | No | false | Download cover images |

Output fields: `id`, `text`, `createTime`, `authorMeta` (name, fans, following, heart, video, verified), `musicMeta`, `covers`, `webVideoUrl`, `videoUrl`, `diggCount`, `shareCount`, `playCount`, `commentCount`, `hashtags`, `mentions`, `isAd`, `isPinned`

Notes:
- `diggCount` = likes (TikTok terminology)
- Video URLs are temporary -- download promptly or they expire
- Video downloads dramatically increase cost and time

### Profile -- `clockworks/tiktok-profile-scraper`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `profiles` | array[string] | Yes | -- | TikTok usernames (without @) |

Output fields: `id`, `uniqueId`, `nickname`, `avatar`, `signature`, `verified`, `bioLink`, `fans`, `following`, `heart`, `video`, `digg`

---

## Instagram

### Posts -- `apify/instagram-post-scraper`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `username` | string | Yes | -- | Instagram username |
| `resultsLimit` | integer | No | 50 | Maximum posts to return |

Output fields: `id`, `type`, `shortCode`, `caption`, `hashtags`, `mentions`, `url`, `commentsCount`, `likesCount`, `videoViewCount`, `timestamp`, `ownerUsername`, `displayUrl`, `images`, `videoUrl`

### Profile -- `apify/instagram-profile-scraper`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `usernames` | array[string] | Yes | -- | Instagram usernames |

Output fields: `id`, `username`, `fullName`, `biography`, `externalUrl`, `followersCount`, `followsCount`, `postsCount`, `isVerified`, `isBusinessAccount`, `profilePicUrl`

### General -- `apify/instagram-scraper`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `directUrls` | array[string] | One of | -- | Profile URLs, post URLs, or hashtag URLs |
| `search` | string | One of | -- | Search query |
| `searchType` | string | No | -- | `hashtag`, `user`, `place` |
| `resultsLimit` | integer | No | 50 | Maximum items |
| `resultsType` | string | No | `posts` | `posts`, `comments`, `details` |

Output fields: `id`, `type`, `shortCode`, `caption`, `hashtags`, `mentions`, `url`, `commentsCount`, `likesCount`, `videoViewCount`, `timestamp`, `ownerUsername`, `ownerId`, `displayUrl`, `images`, `videoUrl`, `locationName`, `isSponsored`, `isPinned`

Notes:
- Private profiles return no data (empty results, no error)
- Residential proxies required -- Instagram aggressively rate-limits
- Reels returned as posts with `type: "Video"`

---

## YouTube

### Channel -- `streamers/youtube-channel-scraper`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `startUrls` | array[object] | Yes | -- | Channel URLs as `{url: "..."}` |
| `maxResults` | integer | No | 50 | Maximum videos to return |

Output fields: `id`, `title`, `url`, `viewCount`, `date`, `likes`, `channelName`, `channelUrl`, `duration`, `description`, `thumbnailUrl`

### Search -- `streamers/youtube-scraper`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `searchKeywords` | array[string] | One of | -- | Search terms |
| `startUrls` | array[object] | One of | -- | Video/channel URLs |
| `maxResults` | integer | No | 50 | Maximum results |

Output fields: `id`, `title`, `url`, `viewCount`, `date`, `likes`, `channelName`, `channelUrl`, `duration`, `description`, `thumbnailUrl`

---

## Cross-Platform Field Mapping

| Concept | TikTok | Instagram | YouTube |
|---------|--------|-----------|---------|
| Likes | `diggCount` | `likesCount` | `likes` |
| Comments | `commentCount` | `commentsCount` | -- |
| Shares | `shareCount` | -- | -- |
| Views | `playCount` | `videoViewCount` | `viewCount` |
