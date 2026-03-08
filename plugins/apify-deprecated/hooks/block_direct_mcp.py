# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
PreToolUse hook — blocks direct Apify MCP tool calls.

Claude must use skills (which use scripts) instead of calling MCP tools directly.
This is the hard enforcement layer — the CLAUDE.md instruction is the soft layer.
"""

import json
import sys


def deny(reason: str):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Block any MCP tool from the Apify server
    if "apify" in tool_name.lower() and tool_name.startswith("mcp"):
        deny(
            "BLOCKED: Direct Apify MCP tool use is not allowed. "
            "You MUST invoke the appropriate skill first: "
            "apify-social-media (Instagram/TikTok/Twitter/Facebook), "
            "apify-ecommerce (Amazon/Shopify/products), "
            "apify-maps (Google Maps/reviews), "
            "apify-discover (unknown platforms). "
            "Skills contain actor mappings, cost gates, and workflow rules. "
            "Using MCP tools directly bypasses all safety guardrails."
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
