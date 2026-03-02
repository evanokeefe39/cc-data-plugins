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

## Four Gates (mandatory before any dispatch)

All four must pass. No exceptions. Enforced by three layers: skill instructions (soft), PreToolUse hook (hard), script validation (hard).

1. **Params Complete** — All required actor parameters resolved, item limit set (`maxItems`/`resultsLimit`/etc.), no vague inputs
2. **Cost Approved** — Estimate presented and explicitly confirmed by user, approval timestamp recorded
3. **Scope Decided** — `metadata_only`, `with_media`, or `with_transcripts`
4. **Destination Set** — `local_duckdb`, `local_files`, `remote`, or `decide_later`

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

## API Token

When `session_start.py` returns `"status": "setup_required"`, the Apify API token is missing. Guide the user:
1. Sign up at https://apify.com/sign-up if needed (free tier available)
2. Get API token from https://console.apify.com/account/integrations
3. Save to project `.env` file: `APIFY_TOKEN=apify_api_XXXXX`
4. Add `.env` to `.gitignore`
5. Restart the Claude Code session

Never ask the user to paste their token into chat. Direct them to `.env` or shell environment only.

Note: The Apify MCP server uses separate OAuth (browser sign-in) and works independently of this token.
