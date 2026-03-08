/**
 * PreToolUse hook — blocks direct Apify search-actors calls.
 *
 * The social-media skill uses hardcoded actors and never needs search.
 * Blocking search-actors prevents Claude from bypassing the skill
 * and going directly to the MCP server for actor discovery.
 */

const data = JSON.parse(require("fs").readFileSync("/dev/stdin", "utf8"));
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
  process.exit(0);
}

process.exit(0);
