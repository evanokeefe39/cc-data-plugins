/**
 * SessionStart hook — ensures .claude/settings.json has required permissions.
 * Creates, merges, or skips as needed. Informs the user of any changes.
 */

const fs = require("fs");
const path = require("path");

const REQUIRED_RULES = ["Bash(node *)", "Bash(mkdir *)", "Read"];

const cwd = process.cwd();
const claudeDir = path.join(cwd, ".claude");
const settingsPath = path.join(claudeDir, "settings.json");

function run() {
  let settings = null;
  let existed = false;

  // Read existing settings if present
  if (fs.existsSync(settingsPath)) {
    existed = true;
    try {
      settings = JSON.parse(fs.readFileSync(settingsPath, "utf8"));
    } catch (e) {
      // Can't parse — report conflict and bail
      console.error(
        "[apify plugin] .claude/settings.json exists but is not valid JSON. " +
        "Please fix it manually or delete it so the plugin can recreate it."
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
    console.error(
      "[apify plugin] .claude/settings.json has deny rules that conflict with " +
      "required permissions: " + conflicts.join(", ") + ". " +
      "The plugin may prompt for permissions until these conflicts are resolved."
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
    console.error(
      "[apify plugin] Created .claude/settings.json with permissions for this " +
      "plugin to run Node scripts and read reference files without prompting. " +
      "You can review or revoke these at any time."
    );
  } else {
    console.error(
      "[apify plugin] Added permissions to your existing .claude/settings.json: " +
      missing.join(", ") + ". You can review or revoke these at any time."
    );
  }
}

run();
