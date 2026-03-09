/**
 * PreToolUse hook — auto-approves Read calls for plugin files.
 * Prevents permission prompts when the skill reads its own references.
 */

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", () => {
  try {
    const data = JSON.parse(input);
    const filePath = (data.tool_input && data.tool_input.file_path) || "";

    // Approve reads of plugin cache files
    if (filePath.includes("cc-data-plugins") && filePath.includes("apify")) {
      const out = {
        hookSpecificOutput: {
          hookEventName: "PreToolUse",
          permissionDecision: "allow",
          permissionDecisionReason: "Plugin reading its own files.",
        },
      };
      process.stdout.write(JSON.stringify(out));
      process.exit(0);
      return;
    }
  } catch (e) {
    // Parse error — allow through to normal permission system
  }
  process.exit(0);
});
