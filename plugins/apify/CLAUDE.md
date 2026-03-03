## Apify Claude Code Plugin — Development

Full spec: https://www.notion.so/Apify-Claude-Code-Plugin-30d6b8a97052813bb14cc49727fa1676
Best Practices for Skills and Plugins: https://www.notion.so/Claude-Code-Skills-Research-Best-Practices-30c6b8a970528196b582f3de2b4a79e4
Complete Guide to Building Skill For Claude: C:\Users\evano\repos\cc-data-plugins\The-Complete-Guide-to-Building-Skill-for-Claude (1).pdf

### Architecture
- DuckDB state backbone with 5 tables: pipeline_runs, apify_jobs, landed_data, _catalog, _diagnostics
- Four-gate enforcement: params, cost, scope, destination

### Tech Stack
Claude Code, Apify REST API + MCP (@apify/actors-mcp-server), Python 3.11, DuckDB, uv

### Key Files
- `scripts/` — 8 PEP 723 Python scripts (session_start, run_actors, estimate_cost, fetch_dataset, import_dataset, query_dataset, check_account_health, install)
- `skills/` — 5 domain skills (social-media, ecommerce, maps, discover, maintenance)
- `hooks/hooks.json` — SessionStart + PreToolUse cost gate
- `hooks/pre_tool_use_cost_gate.py` — Layer 2 hard gate
- `template/CLAUDE-snippet.md` — Content injected into user's project CLAUDE.md
- `.mcp.json` — Apify MCP server config
