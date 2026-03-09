/**
 * SessionStart hook — ensures .claude/settings.json has required permissions.
 * Creates, merges, or skips as needed. Outputs JSON to stdout so Claude
 * can relay messages to the user.
 */

const fs = require("fs");
const path = require("path");

const REQUIRED_RULES = ["Bash(node *)", "Bash(mkdir *)", "Read"];

const cwd = process.cwd();
const claudeDir = path.join(cwd, ".claude");
const settingsPath = path.join(claudeDir, "settings.json");

function output(message) {
  const out = {
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: message,
    },
  };
  process.stdout.write(JSON.stringify(out));
}

function run() {
  let settings = null;
  let existed = false;

  // Read existing settings if present
  if (fs.existsSync(settingsPath)) {
    existed = true;
    try {
      settings = JSON.parse(fs.readFileSync(settingsPath, "utf8"));
    } catch (e) {
      output(
        "[apify plugin] .claude/settings.json exists but is not valid JSON. " +
        "Please tell the user to fix it manually or delete it so the plugin can recreate it."
      );
      return;
    }
  }

  if (!settings) {
    settings = {};
  }

  if (!settings.permissions) {
    settings.permissions = {};
  }

  if (!Array.isArray(settings.permissions.allow)) {
    settings.permissions.allow = [];
  }

  // Check for conflicts — deny rules that would block our requirements
  const denyRules = Array.isArray(settings.permissions.deny) ? settings.permissions.deny : [];
  const conflicts = [];
  for (const rule of REQUIRED_RULES) {
    const keyword = rule.split("(")[0]; // "Bash" or "Read"
    const hasConflict = denyRules.some((d) => d.startsWith(keyword));
    if (hasConflict) {
      conflicts.push(rule);
    }
  }

  if (conflicts.length > 0) {
    output(
      "[apify plugin] .claude/settings.json has deny rules that conflict with " +
      "required permissions: " + conflicts.join(", ") + ". " +
      "Ask the user how they want to resolve these conflicts. " +
      "The plugin may prompt for permissions until they are resolved."
    );
    return;
  }

  // Merge missing rules
  const missing = REQUIRED_RULES.filter((r) => !settings.permissions.allow.includes(r));

  if (missing.length === 0) {
    // All rules present — nothing to do
    return;
  }

  settings.permissions.allow.push(...missing);

  // Ensure .claude directory exists
  if (!fs.existsSync(claudeDir)) {
    fs.mkdirSync(claudeDir, { recursive: true });
  }

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2) + "\n");

  if (!existed) {
    output(
      "[apify plugin] Created .claude/settings.json with permissions to run " +
      "Node scripts and read reference files without prompting. " +
      "Tell the user what was created and that they can review or revoke " +
      "these permissions at any time. " +
      "IMPORTANT: Tell the user to restart Claude Code for the new permissions to take effect."
    );
  } else {
    output(
      "[apify plugin] Added permissions to existing .claude/settings.json: " +
      missing.join(", ") + ". " +
      "Tell the user what was added and that they can review or revoke " +
      "these permissions at any time. " +
      "IMPORTANT: Tell the user to restart Claude Code for the new permissions to take effect."
    );
  }
}

run();
