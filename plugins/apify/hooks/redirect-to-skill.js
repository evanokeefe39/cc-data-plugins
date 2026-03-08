/**
 * PreToolUse hook — intercepts ToolSearch calls that try to load Apify
 * discovery/search tools directly, redirecting Claude to use the
 * social-media skill instead.
 *
 * Allows ToolSearch for execution tools (fetch-actor-details, call-actor,
 * get-actor-run, get-actor-output) since those are called BY the skill workflow.
 */

const ALLOWED_TOOLS = [
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
    const query = (data.tool_input && data.tool_input.query) || "";

    // Only act on apify-related ToolSearch queries
    if (!query.toLowerCase().includes("apify")) {
      process.exit(0);
      return;
    }

    // Allow loading execution tools the skill workflow needs
    const isAllowed = ALLOWED_TOOLS.some((t) => query.includes(t));
    if (isAllowed) {
      process.exit(0);
      return;
    }

    // Block discovery/search tool loading — redirect to skill
    const out = {
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason:
          "BLOCKED: Do not load Apify search/discovery tools directly. " +
          "Use the Skill tool to invoke apify:social-media instead. " +
          "Example: Skill({ skill: 'apify:social-media', args: '<user request>' }). " +
          "The skill contains hardcoded actor mappings, cost gates, and the full planning workflow.",
      },
    };
    process.stdout.write(JSON.stringify(out));
  } catch (e) {
    // Parse error — allow through
  }
  process.exit(0);
});
