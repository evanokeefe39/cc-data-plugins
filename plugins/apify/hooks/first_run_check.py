# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.1.0",
# ]
# ///
"""
UserPromptSubmit hook — checks if first-run onboarding is needed.

If no onboarding_complete key in _user_config (first run), outputs instruction
for Claude to ask setup questions before handling the user's request. Runs on
every user message but exits silently once config exists (near-zero overhead).
"""

import json
import os
import sys
from pathlib import Path

import duckdb

# Add scripts dir to path for shared modules
sys.path.insert(0, str(Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).parent.parent)) / "scripts"))
from _log import log

def _resolve_project_dir() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    cwd = Path.cwd()
    if (cwd / ".apify_plugin").exists():
        return cwd
    print(json.dumps({"error": "CLAUDE_PROJECT_DIR not set and .apify_plugin/ not found in cwd", "cwd": str(cwd)}), file=sys.stderr)
    sys.exit(1)

PROJECT_DIR = _resolve_project_dir()
DATA_DIR = PROJECT_DIR / ".apify_plugin" / "data"
DB_PATH = DATA_DIR / "datasets.duckdb"


def main():
    log("first_run_check", "hook fired")

    # Fast path: DB exists, check onboarding status
    if DB_PATH.exists():
        try:
            con = duckdb.connect(str(DB_PATH), read_only=True)
            result = con.execute(
                "SELECT value FROM _user_config WHERE key = 'onboarding_complete'"
            ).fetchone()
            con.close()
            if result and result[0] and result[0].lower() == "true":
                log("first_run_check", "onboarding complete — skipping")
                return  # Silent exit — no output, no overhead
        except duckdb.CatalogException:
            # Table doesn't exist yet (schema not initialized)
            pass
        except Exception:
            pass

    # Check for API token — only in env vars and project .env (not plugin root)
    token_found = bool(
        os.environ.get("APIFY_TOKEN")
        or os.environ.get("APIFY_API_TOKEN")
    )
    if not token_found:
        env_path = PROJECT_DIR / ".env"
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    if key.strip() in ("APIFY_TOKEN", "APIFY_API_TOKEN") and value.strip().strip("\"'"):
                        token_found = True
                        break
            except Exception:
                pass

    log("first_run_check", f"token_found={token_found}, db_exists={DB_PATH.exists()}")

    # Priority 1: Token setup (blocks everything else)
    if not token_found:
        env_path = PROJECT_DIR / ".env"
        print(
            "STOP. The Apify API token is not configured. Do NOT ask profile questions or proceed with any scraping.\n"
            "Walk the user through these setup steps:\n\n"
            "Step 1 — Authenticate the Apify MCP server:\n"
            "  The Apify MCP server should prompt for OAuth sign-in automatically.\n"
            "  If it hasn't, ask the user to approve the MCP connection when prompted.\n"
            "  This gives Claude access to Apify's actor store and search.\n\n"
            "Step 2 — Get an API token for the plugin scripts:\n"
            "  The plugin scripts (cost estimation, job dispatch, data download) need a REST API token.\n"
            "  1. Go to https://console.apify.com/account/integrations\n"
            "     (sign up at https://apify.com/sign-up if needed — free tier available)\n"
            "  2. Copy the Personal API token\n"
            f"  3. Create or edit {env_path} and add: APIFY_TOKEN=apify_api_XXXXX\n"
            "  4. Make sure .env is in .gitignore\n"
            "  5. Restart this Claude Code session after setting the token.\n\n"
            "Tell the user you'll ask a couple quick setup questions after the token is configured."
        )
        return

    # Priority 2: Profile onboarding (only after token is confirmed)
    # Ensure data dir exists so DuckDB file can be created
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).parent.parent))
    print(
        "This is the user's first session with the Apify plugin. "
        "Ask them these two quick setup questions using AskUserQuestion:\n"
        "1. What's your role? (Developer/Technical, Data Analyst, Marketing/Business, Researcher, Other)\n"
        "2. Where should extracted data go by default? (DuckDB local database, JSON files local, Decide each time)\n\n"
        "After they answer, save their config by running this exact command:\n"
        f'uv run "{plugin_root}/scripts/save_config.py" '
        '--set "role=THEIR_ROLE" --set "default_destination=THEIR_CHOICE" --set "onboarding_complete=true"\n\n'
        "Then proceed to handle their original request."
    )


if __name__ == "__main__":
    main()
