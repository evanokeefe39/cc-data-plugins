## Apify Claude Code Plugin — Development

Full spec: https://www.notion.so/Apify-Claude-Code-Plugin-30d6b8a97052813bb14cc49727fa1676

### Architecture
- Skills = knowledge layer, main thread = orchestrator, no subagents
- Python scripts (PEP 723 via `uv run`) handle all deterministic work
- DuckDB state backbone with 5 tables: pipeline_runs, apify_jobs, landed_data, _catalog, _diagnostics
- Four-gate enforcement: params, cost, scope, destination
- Three-layer enforcement: skill instructions (soft) + PreToolUse hook (hard) + script validation (hard)
- Data never passes through LLM context — scripts stream to files

### Tech Stack
Claude Code, Apify REST API + MCP (@apify/actors-mcp-server), Python 3.11, DuckDB, uv

### Key Files
- `scripts/` — 8 PEP 723 Python scripts (session_start, run_actors, estimate_cost, fetch_dataset, import_dataset, query_dataset, check_account_health, install)
- `skills/` — 5 domain skills (social-media, ecommerce, maps, discover, maintenance)
- `hooks/hooks.json` — SessionStart + PreToolUse cost gate
- `hooks/pre_tool_use_cost_gate.py` — Layer 2 hard gate
- `template/CLAUDE-snippet.md` — Content injected into user's project CLAUDE.md
- `.mcp.json` — Apify MCP server config

### Conventions
- All scripts use `$CLAUDE_PLUGIN_ROOT` for portable paths
- All scripts output JSON to stdout
- Hook uses exit code 2 to block tool calls
- Skills use imperative form, third-person descriptions, progressive disclosure
