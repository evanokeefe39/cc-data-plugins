# Social Media Error Handling Reference

## Common Error Patterns by Platform

### Instagram

| Error | Cause | Recovery |
|-------|-------|----------|
| 403 Forbidden | Anti-bot detection triggered | Already uses residential proxy. Reduce `resultsLimit`, add delays between requests, or try at a different time |
| Empty results (no error) | Private profile or non-existent account | Inform user the profile may be private. No retry will help |
| Timeout after 15+ minutes | Too many items requested | Reduce `resultsLimit` to 50, retry |
| `LOGIN_REQUIRED` | Instagram requiring authentication for this content | Inform user this content requires login. Suggest alternative approach or different content |
| Partial results | Rate limiting mid-scrape | Accept partial results, inform user. Can run again for remaining items |

### TikTok

| Error | Cause | Recovery |
|-------|-------|----------|
| Actor crash / restart | TikTok API changes frequently | Check if actor has updates. Try with fewer profiles |
| Empty results for valid user | TikTok geo-blocking or API changes | Try different proxy region if available. Check actor changelog |
| Video download failures | Temporary URLs expired during download | Re-run with `shouldDownloadVideos: true` for specific posts |
| `BLOCKED` status | TikTok anti-scraping | Reduce concurrency, retry with delays |

### Twitter/X

| Error | Cause | Recovery |
|-------|-------|----------|
| Rate limited (429) | Too many concurrent requests | Wait 15 minutes, retry with lower `maxItems` |
| Empty search results | Query too specific or no matching tweets | Broaden search terms, remove filters |
| `SUSPENDED` in results | Account suspended | Skip account, inform user |
| Incomplete thread data | Thread traversal depth limit | Accept available data, note limitation |

### Facebook

| Error | Cause | Recovery |
|-------|-------|----------|
| 403 / blocked | Anti-scraping measures | Switch to residential proxy if not already. Reduce scope |
| `GROUP_RESTRICTED` | Group requires membership | Inform user — cannot scrape private groups without login |
| Stale URLs | Page renamed or removed | Verify URL manually, update if renamed |
| Comments timeout | `commentsMode: ALL` on viral posts | Switch to `LATEST_10`, inform user |

## Error Message Templates

### Non-Technical User

```
The [platform] extraction couldn't complete for [X] of [Y] [profiles/searches].

What happened: [plain language explanation]

Recommended next step: [specific action]

Options:
1. Retry with the [N] that worked
2. Adjust the request and try again
3. Skip and move on
```

### Technical User

```
Run `[apify_run_id]` failed: [error code] on [X]/[Y] targets.
Cause: [specific technical reason]
Console: https://console.apify.com/actors/runs/[run_id]

Options:
1. Retry partial (exclude failed targets)
2. Retry with adjustments (proxy: residential, maxItems: 50)
3. Skip
4. Investigate in Apify console
```

## Retry Decision Tree

1. Is the error transient (rate limit, timeout)? → Wait briefly, retry same plan through four gates
2. Is it a permanent block (private profile, auth required)? → Inform user, no retry
3. Is it partial success? → Present what worked, offer to retry failed portion as new plan
4. Is the actor deprecated? → Refresh registry, suggest alternative actor
5. Unknown error? → Present raw error, link to Apify console, let user decide
