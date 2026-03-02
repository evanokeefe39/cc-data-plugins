"""Shared debug logger for plugin hooks and scripts.

Writes to .apify_plugin/data/plugin.log in the project directory.
Set APIFY_PLUGIN_DEBUG=1 to enable, or it's always on if the log file already exists.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd()))
LOG_FILE = PROJECT_DIR / ".apify_plugin" / "data" / "plugin.log"

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
