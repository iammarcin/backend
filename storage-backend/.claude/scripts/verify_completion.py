#!/usr/bin/env python3
"""Stop hook to verify task completion before Claude stops.

This script runs when Claude is about to complete a response to:
1. Verify that tests pass (if changes were made to source files)
2. Check for incomplete work markers (TODO, FIXME)
3. Ensure no syntax errors in modified files

Exit codes:
- 0: Allow completion
- Output JSON with "decision": "block" to force continuation
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    """Run command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as exc:
        return -1, "", str(exc)


def check_tests() -> tuple[bool, str]:
    """Check if tests pass."""
    # Try running tests in Docker container
    returncode, stdout, stderr = run_command(
        ["docker", "exec", "backend", "pytest", "tests/", "-x", "--tb=no", "-q"],
        timeout=120,
    )

    if returncode == 0:
        return True, ""

    # Tests failed - return last 500 chars of output
    output = (stdout + stderr)[-500:]
    return False, f"Tests are failing:\n{output}"


def check_git_status() -> tuple[bool, str]:
    """Check git status for incomplete work markers."""
    returncode, stdout, _ = run_command(["git", "status", "--porcelain"])

    if returncode != 0:
        return True, ""  # Can't check, allow

    if not stdout.strip():
        return True, ""  # No changes, allow

    # Check changed files for TODO/FIXME markers
    changed_files = []
    for line in stdout.strip().split("\n"):
        if line.strip():
            # Parse git status format: "XY filename"
            parts = line.split(maxsplit=1)
            if len(parts) >= 2:
                changed_files.append(parts[1].strip())

    # Look for TODO/FIXME in changed Python files
    for file_path in changed_files:
        if file_path.endswith(".py") and Path(file_path).exists():
            try:
                content = Path(file_path).read_text()
                if "TODO:" in content or "FIXME:" in content:
                    return False, f"Found TODO/FIXME markers in {file_path}"
            except Exception:
                pass

    return True, ""


def check_syntax() -> tuple[bool, str]:
    """Run ruff check on changed files."""
    returncode, stdout, _ = run_command(["git", "diff", "--name-only", "HEAD"])

    if returncode != 0:
        return True, ""  # Can't check, allow

    python_files = [f for f in stdout.strip().split("\n") if f.endswith(".py")]

    if not python_files:
        return True, ""  # No Python files changed

    # Run ruff check
    returncode, stdout, stderr = run_command(
        ["docker", "exec", "backend", "ruff", "check"] + python_files,
        timeout=30,
    )

    if returncode == 0:
        return True, ""

    output = (stdout + stderr)[-300:]
    return False, f"Linting errors detected:\n{output}"


def block_completion(reason: str) -> None:
    """Output block response and exit."""
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def main() -> None:
    """Main entry point for the completion verification hook."""
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        data = {}

    # Prevent infinite loops - if stop hook already active, allow
    if data.get("stop_hook_active"):
        sys.exit(0)

    # Check git status for incomplete work
    status_ok, status_reason = check_git_status()
    if not status_ok:
        block_completion(status_reason)

    # Check syntax/linting
    syntax_ok, syntax_reason = check_syntax()
    if not syntax_ok:
        block_completion(syntax_reason)

    # Check tests - this is the most important check
    tests_ok, test_reason = check_tests()
    if not tests_ok:
        block_completion(test_reason)

    # All checks passed - allow completion
    sys.exit(0)


if __name__ == "__main__":
    main()
