/**
 * PreToolUse hook — blocks Apify search/discovery MCP tool calls from
 * BOTH namespaces (mcp__plugin_apify_apify__* and mcp__claude_ai_apify__*).
 *
 * Allows execution tools: fetch-actor-details, call-actor, get-actor-run,
 * get-actor-output, get-dataset-items (needed by the skill workflow).
 *
 * Blocks: search-actors, search-apify-docs, apify-slash-rag-web-browser,
 * and any other discovery/browsing tools.
 */

const ALLOWED_SUFFIXES = [
  "fetch-actor-details",
  "call-actor",
  "get-actor-run",
  "get-actor-output",
  "get-dataset-items",
];

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", () => {
  try {
    const data = JSON.parse(input);
    const tool = data.tool_name || "";

    // Only act on apify MCP tools
    if (!tool.includes("apify")) {
      process.exit(0);
      return;
    }

    // Allow execution tools the skill workflow uses
    const isAllowed = ALLOWED_SUFFIXES.some((suffix) => tool.endsWith(suffix));
    if (isAllowed) {
      process.exit(0);
      return;
    }

    // Block everything else (search-actors, search-apify-docs, rag-web-browser, etc.)
    const out = {
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason:
          "BLOCKED: Direct Apify discovery tools are not allowed. " +
          "All actors are hardcoded in the social-media skill. " +
          "Use the Skill tool to invoke apify:social-media first. " +
          "Example: Skill({ skill: 'apify:social-media', args: '<user request>' }). " +
          "The skill will instruct you which MCP tools to call and when.",
      },
    };
    process.stdout.write(JSON.stringify(out));
  } catch (e) {
    // Parse error — allow through
  }
  process.exit(0);
});
