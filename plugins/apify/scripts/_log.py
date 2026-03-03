"""Shared debug logger and project dir resolution for plugin hooks and scripts.

Writes to .apify-plugin/data/plugin.log in the project directory.
Set APIFY_PLUGIN_DEBUG=1 to enable, or it's always on if the log file already exists.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_project_dir() -> Path:
    """Resolve the user's project directory.

    Uses CLAUDE_PROJECT_DIR env var (set by Claude Code for hooks and Bash).
    Falls back to cwd only if .apify-plugin/ exists there.
    Exits with a clear error if neither works — prevents silently using
    the plugin cache dir as the project dir.
    """
    env_val = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_val:
        return Path(env_val)
    cwd = Path.cwd()
    if (cwd / ".apify-plugin").exists():
        return cwd
    print(
        json.dumps({
            "error": "CLAUDE_PROJECT_DIR not set and .apify-plugin/ not found in cwd",
            "cwd": str(cwd),
            "hint": "Run this script from your project directory or set CLAUDE_PROJECT_DIR",
        }),
        file=sys.stderr,
    )
    sys.exit(1)


PROJECT_DIR = get_project_dir()
LOG_FILE = PROJECT_DIR / ".apify-plugin" / "data" / "plugin.log"

_enabled = None


def _is_enabled() -> bool:
    global _enabled
    if _enabled is None:
        _enabled = os.environ.get("APIFY_PLUGIN_DEBUG") == "1" or LOG_FILE.exists()
    return _enabled


def log(source: str, message: str):
    """Append a timestamped log line. No-op if debug is off."""
    if not _is_enabled():
        return
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {source}: {message}\n")
    except Exception:
        pass
