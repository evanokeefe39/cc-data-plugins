# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
PermissionRequest hook — fallback auto-approve for plugin scripts.

Fires when a permission dialog is about to appear. If the command
runs a known plugin script via `uv run`, auto-allows it so the
user is never prompted for routine plugin operations.
"""

import json
import sys

PLUGIN_SCRIPTS = [
    "session_start.py",
    "query_dataset.py",
    "run_actors.py",
    "estimate_cost.py",
    "fetch_dataset.py",
    "import_dataset.py",
    "check_account_health.py",
    "save_config.py",
    "install.py",
]


def main():
    try:
        stdin_data = sys.stdin.read()
        tool_input = json.loads(stdin_data)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    tool_name = tool_input.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    tool_input_data = tool_input.get("tool_input", {})
    command = tool_input_data.get("command", "")

    # Auto-approve known plugin scripts
    if "uv run" in command:
        for script in PLUGIN_SCRIPTS:
            if script in command:
                print(json.dumps({
                    "hookSpecificOutput": {
                        "hookEventName": "PermissionRequest",
                        "decision": {
                            "behavior": "allow"
                        }
                    }
                }))
                sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
