"""Shared Apify token resolution — checks env vars then project .env file."""

import os
from pathlib import Path


def _resolve_project_dir() -> Path:
    """Resolve project directory — env var or cwd with .apify_plugin/ check."""
    if env_dir := os.environ.get("CLAUDE_PROJECT_DIR"):
        return Path(env_dir)
    cwd = Path.cwd()
    if (cwd / ".apify_plugin").exists():
        return cwd
    # For token resolution, cwd is acceptable even without .apify_plugin
    # (user may be setting up for the first time)
    return cwd


PROJECT_DIR = _resolve_project_dir()


def get_apify_token() -> str | None:
    """Get Apify API token from environment or .env file."""
    token = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
    if token:
        return token

    # Check project .env file
    env_file = PROJECT_DIR / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("\"'")
                if key in ("APIFY_TOKEN", "APIFY_API_TOKEN") and value:
                    return value
        except Exception:
            pass

    return None
