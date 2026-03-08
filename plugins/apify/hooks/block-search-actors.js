/**
 * PreToolUse hook — blocks direct Apify search-actors calls.
 *
 * The social-media skill uses hardcoded actors and never needs search.
 * Blocking search-actors prevents Claude from bypassing the skill
 * and going directly to the MCP server for actor discovery.
 */

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", () => {
  try {
    const data = JSON.parse(input);
    const tool = data.tool_name || "";

    if (tool.includes("apify") && tool.includes("search")) {
      const out = {
        hookSpecificOutput: {
          hookEventName: "PreToolUse",
          permissionDecision: "deny",
          permissionDecisionReason:
            "BLOCKED: Do not search for Apify actors. " +
            "All actors are hardcoded in the social-media skill. " +
            "Invoke the skill apify:social-media first, then follow its instructions. " +
            "The skill contains actor mappings, cost gates, and the planning workflow.",
        },
      };
      process.stdout.write(JSON.stringify(out));
    }
  } catch (e) {
    // Parse error — allow the tool call through
  }
  process.exit(0);
});
