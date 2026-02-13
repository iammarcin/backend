#!/usr/bin/env python3
"""PreToolUse hook for security validation.

This script runs before Write/Edit operations to:
1. Block modifications to sensitive files (.env, credentials, secrets)
2. Detect hardcoded secrets in content being written
3. Block modifications to protected directories (migrations)

Exit codes:
- 0: Allow the operation
- 2: Block the operation (with reason in stdout)
"""

from __future__ import annotations

import json
import re
import sys


# Sensitive file patterns (case-insensitive matching)
SENSITIVE_FILE_PATTERNS = [
    r"\.env",
    r"credentials",
    r"secrets?\.?(json|yaml|yml|py)?$",
    r"password",
    r"\.pem$",
    r"\.key$",
    r"api_key",
]

# Protected directories that should not be modified
PROTECTED_PATHS = [
    "migrations/versions/",
    ".git/",
]

# Regex patterns for detecting secrets in content
SECRET_PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI API key"),
    (r"sk-ant-[a-zA-Z0-9-]{20,}", "Anthropic API key"),
    (r"AKIA[A-Z0-9]{16}", "AWS Access Key ID"),
    (r"[a-zA-Z0-9/+]{40}", "AWS Secret Access Key (potential)"),
    (r'password\s*[=:]\s*["\'][^"\']{8,}["\']', "Hardcoded password"),
    (r'api_key\s*[=:]\s*["\'][^"\']{10,}["\']', "Hardcoded API key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
]


def check_sensitive_path(file_path: str) -> tuple[bool, str]:
    """Check if file path matches sensitive patterns."""
    path_lower = file_path.lower()

    for pattern in SENSITIVE_FILE_PATTERNS:
        if re.search(pattern, path_lower, re.IGNORECASE):
            return True, f"Matches sensitive file pattern: {pattern}"

    for protected in PROTECTED_PATHS:
        if protected in file_path:
            return True, f"Path is in protected directory: {protected}"

    return False, ""


def check_content_for_secrets(content: str) -> tuple[bool, str]:
    """Check content for hardcoded secrets."""
    for pattern, description in SECRET_PATTERNS:
        if re.search(pattern, content):
            return True, f"Detected potential {description}"
    return False, ""


def deny_operation(reason: str) -> None:
    """Output denial response and exit."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def main() -> None:
    """Main entry point for the security check hook."""
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # If we can't parse input, allow the operation
        sys.exit(0)

    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # Only check Write and Edit operations
    if tool not in ("Write", "Edit"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")

    # Check for sensitive file paths
    is_sensitive, reason = check_sensitive_path(file_path)
    if is_sensitive:
        deny_operation(f"Cannot modify sensitive file: {file_path} ({reason})")

    # Get content to check
    content = ""
    if tool == "Write":
        content = tool_input.get("content", "")
    elif tool == "Edit":
        content = tool_input.get("new_string", "")

    # Check for secrets in content
    if content:
        has_secret, secret_reason = check_content_for_secrets(content)
        if has_secret:
            deny_operation(f"Content blocked: {secret_reason}")

    # Allow the operation
    sys.exit(0)


if __name__ == "__main__":
    main()
