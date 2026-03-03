# Apify Plugin — Shared Rules & Scripts

This reference is shared across all Apify plugin skills. Load it when executing any extraction workflow.

## CRITICAL: Use Packaged Scripts Only

NEVER write inline Python, ad-hoc DuckDB queries, or custom Bash commands for plugin operations. ALWAYS use the packaged scripts via `uv run scripts/<script>`. These scripts are pre-authorized and will not prompt the user for permission. Inline code WILL trigger permission prompts and break the agentic flow.

Examples:
- `uv run scripts/query_dataset.py sql "SELECT * FROM landed_data"`
- `uv run scripts/query_dataset.py tables`
- `uv run scripts/check_account_health.py --section spending`
- WRONG: `python -c "import duckdb; ..."` — triggers permission prompt
- WRONG: Inline Python or ad-hoc Bash — triggers permission prompt

## Lifecycle

Every data extraction request follows four phases:

1. **INIT** — Automatic on session start. Initializes DuckDB, checks for incomplete runs, loads user profile.
2. **PLAN** — Skill activates on user request. Resolve data needs, select actors, validate params, estimate cost, present four-gate approval.
3. **EXECUTE** — After all four gates pass. Dispatch jobs, download data, import to DuckDB, validate.
4. **REPLAN** — User follow-up after execution. Check existing data FIRST before proposing a new scrape.

## Cost Estimation — Hard Rule

**NEVER invent, guess, or hallucinate cost numbers.** The ONLY way to get cost data is by running `estimate_cost.py`. This script queries the Apify API for real historical run data and returns costs in **USD** (not "credits", not "units", not any other term). If you cannot run the script, say "I need to run the cost estimation script" — never fill in placeholder numbers.

Prohibited patterns:
- "~2 credits" / "~$0.50" / "roughly X" — any cost number not from the script
- The word "credits" — Apify bills in USD per compute usage, not credits
- Presenting a cost table before running `estimate_cost.py`

## Four Gates (mandatory before any dispatch)

All four must pass. No exceptions. Enforced by three layers: skill instructions (soft), PreToolUse hook (hard), script validation (hard).

1. **Params Complete** — All required actor parameters resolved, item limit set (`maxItems`/`resultsLimit`/etc.), no vague inputs
2. **Cost Approved** — Estimate presented and explicitly confirmed by user, approval timestamp recorded
3. **Scope Decided** — `metadata_only`, `with_media`, or `with_transcripts`
4. **Destination Set** — `local_duckdb`, `local_files`, `remote`, or `decide_later`

### Plan JSON format

The plan MUST use this exact structure. Write it to a `.json` file, then pass via `--plan <file>`.

```json
{
  "session_id": "abc-123",
  "user_request": "Get 50 Instagram posts from @natgeo",
  "jobs": [
    {
      "actor_id": "apify/instagram-scraper",
      "input": {
        "directUrls": ["https://www.instagram.com/natgeo/"],
        "resultsType": "posts",
        "resultsLimit": 50
      }
    }
  ],
  "cost_approval": {
    "approved": true,
    "estimated_cost": 0.12,
    "timestamp": "2025-01-15T10:30:00Z"
  },
  "scope": "metadata_only",
  "destination": "local_duckdb"
}
```

Key rules:
- `jobs` is a **required array** — never put `actor_id` at the top level
- Each job needs `actor_id`, `input` with an item limit key, and optionally `timeout_secs`/`build`
- `cost_approval` must have `approved: true` and `timestamp` (ISO-8601)
- Actor IDs use **slash notation** (`apify/instagram-scraper`) — the dispatch script auto-converts to tilde for API calls

## Data Handling Rules

- Data NEVER passes through the LLM context window — scripts stream to files, import to DuckDB
- Check existing data in DuckDB BEFORE proposing any new scrape
- Never auto-land data — always ask user where to put it
- Never auto-delete from Apify — always ask first
- Exclude pinned posts by default on social media scrapes
- Default media downloads to local, not Apify KV (avoids GB-hour costs)

## Error Handling Rules

- No silent retries — inform user and present options
- Retries go through all four gates again (a retry is a new plan)
- Adapt error messages to user profile from CLAUDE.md (technical vs non-technical)

## Script Reference

All scripts run via `uv run scripts/<script>`:

| Script | Purpose | Key Args |
|--------|---------|----------|
| `session_start.py` | Session init, recovery, registry refresh | `--force-refresh`, `--check-registry <query>` |
| `run_actors.py dispatch` | Dispatch jobs (validates all 4 gates) | `--plan <file>` |
| `run_actors.py poll` | Check running job status | `--run-id <id>`, `--job-id <id>` |
| `run_actors.py status` | Full pipeline run status | `<run_id>` |
| `estimate_cost.py` | Cost estimate from Apify API | `--plan <file>` |
| `fetch_dataset.py` | Stream dataset to local files | `--dataset-id <id>`, `--format jsonl\|csv`, `--sanitize` |
| `import_dataset.py` | Import into DuckDB + schema discovery | `--file <path>`, `--actor-slug <actor>`, `--table <name>` |
| `query_dataset.py sql` | Query DuckDB | `"<SQL>"`, `--limit <n>` |
| `query_dataset.py tables` | List all DuckDB tables | — |
| `query_dataset.py catalog` | Show known actor output schemas | — |
| `check_account_health.py` | Storage costs, spending, stale data | `--section all\|account\|storage\|spending\|diagnostics` |

## User Profile

Read the user's profile from the project CLAUDE.md (between `APIFY-PLUGIN:START` and `APIFY-PLUGIN:END` markers). Adapt behavior based on:
- **Role / Skill Level** — technical users get concise output, non-technical get explanations
- **Default Destination** — use as default for Gate 4 if set
- **Tech Stack** — informs data format recommendations
- **Previous Actors Used** — helps with actor selection and schema lookups

## Authentication Setup

The plugin uses two auth mechanisms:

### 1. Apify MCP Server (OAuth)
The MCP server (`@apify/actors-mcp-server`) uses browser-based OAuth sign-in. It should prompt automatically on first use. This gives Claude access to Apify's actor store and search.

### 2. API Token (REST API)
The plugin scripts need a REST API token for dispatching jobs, downloading data, estimating costs, and checking account health.

When `session_start.py` returns `"status": "setup_required"`, guide the user:
1. Authenticate the MCP server first (OAuth prompt should appear automatically)
2. Sign up at https://apify.com/sign-up if needed (free tier available)
3. Get API token from https://console.apify.com/account/integrations
4. Save to project `.env` file: `APIFY_TOKEN=apify_api_XXXXX`
5. Add `.env` to `.gitignore`
6. Restart the Claude Code session

Never ask the user to paste their token into chat. Direct them to `.env` or shell environment only.
