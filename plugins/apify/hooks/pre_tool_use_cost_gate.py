# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
PreToolUse hook — auto-approves plugin file access + Layer 2 cost gate.

Three responsibilities:
1. Auto-approve Bash: Any command running a known plugin script gets
   permissionDecision="allow", bypassing the permission prompt.
2. Auto-approve Read: Any Read of files inside the plugin directory gets
   permissionDecision="allow", bypassing the permission prompt.
3. Cost gate: run_actors.py dispatch commands are validated against all
   4 gates. permissionDecision="deny" on failure.

This hook reads the tool input from stdin (JSON with tool_name and tool_input).
"""

import json
import os
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).parent.parent)).resolve()

# Known plugin scripts — commands containing these are auto-approved
PLUGIN_SCRIPTS = [
    "session_start.py",
    "query_dataset.py",
    "run_actors.py",
    "estimate_cost.py",
    "fetch_dataset.py",
    "import_dataset.py",
    "check_account_health.py",
]


def allow(reason: str):
    """Auto-approve the tool call, bypassing permission prompt."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def deny(reason: str):
    """Block the tool call."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def is_plugin_script(command: str) -> str | None:
    """Check if command runs a known plugin script. Returns script name or None."""
    for script in PLUGIN_SCRIPTS:
        if script in command and "uv run" in command:
            return script
    return None


def extract_plan_path(command: str) -> str | None:
    """Extract --plan argument from a run_actors.py dispatch command."""
    match = re.search(r'--plan\s+["\']?([^\s"\']+)["\']?', command)
    if match:
        return match.group(1)

    match = re.search(r"--plan\s+'(.+?)'", command)
    if match:
        return match.group(1)

    return None


def validate_plan(plan: dict) -> list[str]:
    """Validate plan against all four gates. Returns errors."""
    errors = []

    # Gate 1 — Params Complete
    jobs = plan.get("jobs", [])
    if not jobs:
        errors.append("Gate 1 (Params): No jobs defined in plan.")

    for i, job in enumerate(jobs):
        actor_id = job.get("actor_id")
        if not actor_id:
            errors.append(f"Gate 1 (Params): Job {i} missing actor_id.")
        input_params = job.get("input", {})
        if not input_params:
            errors.append(f"Gate 1 (Params): Job {i} has no input parameters.")
        max_items = (
            input_params.get("maxItems") or
            input_params.get("resultsLimit") or
            input_params.get("resultsPerPage") or
            input_params.get("maxCrawledPlacesPerSearch")
        )
        if max_items is None:
            errors.append(f"Gate 1 (Params): Job {i} ({actor_id}) has no item limit. Never run unbounded.")

    # Gate 2 — Cost Approved
    cost_approval = plan.get("cost_approval")
    if not cost_approval or not cost_approval.get("approved"):
        errors.append("Gate 2 (Cost): Cost not approved by user.")

    # Gate 3 — Scope Decided
    scope = plan.get("scope")
    if scope not in {"metadata_only", "with_media", "with_transcripts"}:
        errors.append(f"Gate 3 (Scope): Invalid or missing scope '{scope}'.")

    # Gate 4 — Destination Set
    destination = plan.get("destination")
    if destination not in {"local_duckdb", "local_files", "remote", "decide_later"}:
        errors.append(f"Gate 4 (Destination): Invalid or missing destination '{destination}'.")

    return errors


def main():
    # Read tool input from stdin
    try:
        stdin_data = sys.stdin.read()
        tool_input = json.loads(stdin_data)
    except (json.JSONDecodeError, Exception):
        # Not JSON input — pass through
        sys.exit(0)

    tool_name = tool_input.get("tool_name", "")
    tool_input_data = tool_input.get("tool_input", {})

    # --- Auto-approve Read of plugin files ---
    if tool_name == "Read":
        file_path = tool_input_data.get("file_path", "")
        try:
            resolved = Path(file_path).resolve()
            if resolved.is_relative_to(PLUGIN_ROOT):
                allow(f"Plugin file: {resolved.name}")
                return
        except (ValueError, OSError):
            pass
        sys.exit(0)

    # Only intercept Bash tool beyond this point
    if tool_name != "Bash":
        sys.exit(0)

    command = tool_input_data.get("command", "")

    # --- Auto-approve known plugin scripts ---
    script = is_plugin_script(command)
    if script:
        # Special case: run_actors.py dispatch needs cost gate validation
        if script == "run_actors.py" and "dispatch" in command:
            pass  # Fall through to cost gate below
        else:
            allow(f"Apify plugin script: {script}")
            return  # never reached, allow() calls sys.exit

    # --- Cost gate: validate run_actors.py dispatch ---
    if "run_actors.py" not in command or "dispatch" not in command:
        sys.exit(0)  # Not a dispatch command — pass through

    plan_path = extract_plan_path(command)
    if not plan_path:
        deny("Cannot validate: no --plan argument found in dispatch command.")
        return

    # Try to load and validate plan
    try:
        if os.path.isfile(plan_path):
            plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
        else:
            plan = json.loads(plan_path)
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        deny(f"Cannot read plan: {e}")
        return

    # Validate all four gates
    errors = validate_plan(plan)

    if errors:
        deny(
            f"Blocked: {len(errors)} gate(s) failed. "
            + "; ".join(errors)
        )
        return

    # All gates pass — approve with cost info
    cost_approval = plan.get("cost_approval", {})
    estimated_cost = cost_approval.get("estimated_cost", "unknown")
    job_count = len(plan.get("jobs", []))

    allow(
        f"4 gates passed — {job_count} job(s), est. ${estimated_cost}"
    )


if __name__ == "__main__":
    main()
