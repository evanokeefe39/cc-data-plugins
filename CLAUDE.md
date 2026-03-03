## CC Data Plugins — Marketplace Development

Best Practices for Skills and Plugins: https://www.notion.so/Claude-Code-Skills-Research-Best-Practices-30c6b8a970528196b582f3de2b4a79e4
Complete Guide to Building Skill For Claude: C:\Users\evano\repos\cc-data-plugins\The-Complete-Guide-to-Building-Skill-for-Claude (1).pdf

### Architecture
- Skills = knowledge layer, main thread = orchestrator, no subagents
- Python scripts (PEP 723 via `uv run`) handle all deterministic work
- Three-layer enforcement: skill instructions (soft) + PreToolUse hook (hard) + script validation (hard)
- Data never passes through LLM context — scripts stream to files

### Conventions
- All scripts use `$CLAUDE_PLUGIN_ROOT` for portable paths
- All scripts output JSON to stdout
- Hook uses exit code 2 to block tool calls
- Skills use imperative form, third-person descriptions, progressive disclosure
