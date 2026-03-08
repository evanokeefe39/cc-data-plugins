## CC Data Plugins -- Marketplace Development

Best Practices for Skills and Plugins: https://www.notion.so/Claude-Code-Skills-Research-Best-Practices-30c6b8a970528196b582f3de2b4a79e4
Complete Guide to Building Skill For Claude: C:\Users\evano\repos\cc-data-plugins\The-Complete-Guide-to-Building-Skill-for-Claude (1).pdf

### Architecture
- Skills = knowledge layer, main thread = orchestrator, no subagents
- Node.js (CommonJS) scripts handle all deterministic work (Phase 2+)
- Data never passes through LLM context -- always written to disk first
- Hardcoded actors only -- no discovery, 7 actors across 3 platforms (TikTok, Instagram, YouTube)
- Live cost from Apify API -- never hardcode cost figures

### Conventions
- All scripts use `$CLAUDE_PLUGIN_ROOT` for portable paths
- All scripts output JSON to stdout
- Hook uses exit code 2 to block tool calls
- Skills use imperative form, third-person descriptions, progressive disclosure

### Plugin Structure
- `plugins/apify/` -- active plugin (v0.1.0, Node.js, social media only)
- `plugins/apify-deprecated/` -- old plugin (v0.2.0, Python/uv, over-engineered, preserved for reference)

## Testing

- We are testing the plugin in ~/repos/apif-test where we have the marketplace installed

## Refactoring
- We are currently refactoring using SPEC-10 in notion spec database for requirements and direction.
- SPEC-6 (MCP Response Interceptor) is deferred -- plugin handles data-to-disk directly.
