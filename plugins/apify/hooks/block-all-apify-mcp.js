/**
 * PreToolUse hook — blocks ALL Apify MCP tool calls.
 * CLI skill uses Apify REST API via scripts, not MCP.
 * No allowlist — every apify MCP tool is blocked.
 */

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", () => {
  try {
    const data = JSON.parse(input);
    const tool = data.tool_name || "";
    const query = (data.tool_input && data.tool_input.query) || "";

    // Block ToolSearch queries for apify tools
    if (data.tool_name === "ToolSearch" && query.toLowerCase().includes("apify")) {
      const out = {
        hookSpecificOutput: {
          hookEventName: "PreToolUse",
          permissionDecision: "deny",
          permissionDecisionReason:
            "BLOCKED: Do not load Apify MCP tools. " +
            "Use the Skill tool to invoke apify:social-media instead. " +
            "Example: Skill({ skill: 'apify:social-media', args: '<user request>' }). " +
            "The skill uses scripts and the Apify REST API directly.",
        },
      };
      process.stdout.write(JSON.stringify(out));
      process.exit(0);
      return;
    }

    // Block direct apify MCP tool calls
    if (tool.includes("apify") && tool.startsWith("mcp__")) {
      const out = {
        hookSpecificOutput: {
          hookEventName: "PreToolUse",
          permissionDecision: "deny",
          permissionDecisionReason:
            "BLOCKED: Direct Apify MCP tools are not used in this plugin. " +
            "Use the Skill tool to invoke apify:social-media instead. " +
            "The skill handles everything via scripts and the Apify REST API.",
        },
      };
      process.stdout.write(JSON.stringify(out));
      process.exit(0);
      return;
    }
  } catch (e) {
    // Parse error — allow through
  }
  process.exit(0);
});
