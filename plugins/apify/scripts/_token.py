"""Shared Apify token resolution — checks env vars then project .env file."""

import os
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd()))


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
