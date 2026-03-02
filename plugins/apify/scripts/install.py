# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Install script — injects plugin snippet into user's project CLAUDE.md.

The snippet content lives in template/CLAUDE-snippet.md and contains:
- Plugin orchestration rules (lifecycle, four gates, data handling)
- User profile placeholder (filled by session_start.py)
- Script reference quick guide
"""

import argparse
import json
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).parent.parent))
SNIPPET_FILE = PLUGIN_ROOT / "template" / "CLAUDE-snippet.md"

# Markers to identify our section in the user's CLAUDE.md
START_MARKER = "<!-- APIFY-PLUGIN:START -->"
END_MARKER = "<!-- APIFY-PLUGIN:END -->"


def load_snippet() -> str:
    """Load the snippet template."""
    if not SNIPPET_FILE.exists():
        print(f"Error: Snippet template not found at {SNIPPET_FILE}")
        sys.exit(1)
    return SNIPPET_FILE.read_text(encoding="utf-8")


def install_snippet(project_dir: Path, force: bool = False) -> dict:
    """Inject snippet into project CLAUDE.md."""
    claude_md = project_dir / "CLAUDE.md"
    snippet = load_snippet()
    wrapped_snippet = f"\n{START_MARKER}\n{snippet}\n{END_MARKER}\n"

    if claude_md.exists():
        existing = claude_md.read_text(encoding="utf-8")

        # Check if already installed
        if START_MARKER in existing:
            if not force:
                return {
                    "status": "already_installed",
                    "message": "Apify plugin snippet already present in CLAUDE.md. Use --force to update.",
                }
            # Replace existing snippet
            start_idx = existing.index(START_MARKER)
            end_idx = existing.index(END_MARKER) + len(END_MARKER)
            updated = existing[:start_idx] + wrapped_snippet.strip() + existing[end_idx:]
            claude_md.write_text(updated, encoding="utf-8")
            return {
                "status": "updated",
                "message": "Apify plugin snippet updated in CLAUDE.md.",
                "path": str(claude_md),
            }
        else:
            # Append to existing
            updated = existing.rstrip() + "\n\n" + wrapped_snippet
            claude_md.write_text(updated, encoding="utf-8")
            return {
                "status": "appended",
                "message": "Apify plugin snippet appended to existing CLAUDE.md.",
                "path": str(claude_md),
            }
    else:
        # Create new CLAUDE.md
        claude_md.write_text(wrapped_snippet.lstrip(), encoding="utf-8")
        return {
            "status": "created",
            "message": "Created CLAUDE.md with Apify plugin snippet.",
            "path": str(claude_md),
        }


def uninstall_snippet(project_dir: Path) -> dict:
    """Remove snippet from project CLAUDE.md."""
    claude_md = project_dir / "CLAUDE.md"

    if not claude_md.exists():
        return {"status": "not_found", "message": "No CLAUDE.md found."}

    existing = claude_md.read_text(encoding="utf-8")

    if START_MARKER not in existing:
        return {"status": "not_installed", "message": "Apify plugin snippet not found in CLAUDE.md."}

    start_idx = existing.index(START_MARKER)
    end_idx = existing.index(END_MARKER) + len(END_MARKER)

    # Remove snippet and clean up whitespace
    updated = existing[:start_idx].rstrip() + "\n" + existing[end_idx:].lstrip()
    updated = updated.strip()

    if updated:
        claude_md.write_text(updated + "\n", encoding="utf-8")
        return {"status": "removed", "message": "Apify plugin snippet removed from CLAUDE.md."}
    else:
        claude_md.unlink()
        return {"status": "deleted", "message": "CLAUDE.md was empty after removal — deleted file."}


def main():
    parser = argparse.ArgumentParser(description="Install/uninstall Apify plugin CLAUDE.md snippet")
    parser.add_argument("action", choices=["install", "uninstall"], help="Action to perform")
    parser.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR", "."),
                        help="Path to user's project directory")
    parser.add_argument("--force", action="store_true", help="Force update if already installed")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()

    if args.action == "install":
        result = install_snippet(project_dir, args.force)
    else:
        result = uninstall_snippet(project_dir)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
