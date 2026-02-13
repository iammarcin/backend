#!/usr/bin/env python3
"""Update automation request status via API.

This script is used by custom commands and hooks to update request status.

Usage:
    python3 update_request_status.py <request_id> --status implementing
    python3 update_request_status.py <request_id> --status implementing --phase M1
    python3 update_request_status.py <request_id> --status failed --error "Tests failed"
    python3 update_request_status.py <request_id> --milestones milestones.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.parse import urljoin

import requests


def get_api_base() -> str:
    """Get the API base URL from environment."""
    return os.getenv("AUTOMATION_API_BASE", "http://localhost:8000")


def update_status(
    request_id: str,
    status: str | None = None,
    phase: str | None = None,
    error: str | None = None,
) -> bool:
    """Update request status via the convenience endpoint."""
    base_url = get_api_base()
    url = urljoin(base_url, f"/api/v1/automation/requests/{request_id}/status")

    params = {}
    if status:
        params["status"] = status
    if phase:
        params["phase"] = phase
    if error:
        params["error"] = error

    try:
        response = requests.patch(url, params=params, timeout=10)
        response.raise_for_status()
        print(f"Status updated: {status}")
        return True
    except requests.RequestException as exc:
        print(f"Error updating status: {exc}", file=sys.stderr)
        return False


def update_request(request_id: str, updates: dict) -> bool:
    """Update request via the PATCH endpoint."""
    base_url = get_api_base()
    url = urljoin(base_url, f"/api/v1/automation/requests/{request_id}")

    try:
        response = requests.patch(url, json=updates, timeout=10)
        response.raise_for_status()
        print(f"Request updated: {list(updates.keys())}")
        return True
    except requests.RequestException as exc:
        print(f"Error updating request: {exc}", file=sys.stderr)
        return False


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Update automation request status")
    parser.add_argument("request_id", help="Request ID to update")
    parser.add_argument("--status", help="New status value")
    parser.add_argument("--phase", help="Current processing phase")
    parser.add_argument("--error", help="Error message if failed")
    parser.add_argument("--milestones", help="JSON file or string with milestones")
    parser.add_argument("--session-id", help="Claude Code session ID")
    parser.add_argument("--plan", help="Plan document content or file path")
    parser.add_argument("--pr-url", help="Pull request URL")
    parser.add_argument("--test-results", help="Test results JSON")

    args = parser.parse_args()

    # Simple status update
    if args.status and not any([args.milestones, args.session_id, args.plan, args.pr_url]):
        success = update_status(
            args.request_id,
            status=args.status,
            phase=args.phase,
            error=args.error,
        )
        sys.exit(0 if success else 1)

    # Complex update with multiple fields
    updates = {}

    if args.status:
        updates["status"] = args.status
    if args.phase:
        updates["current_phase"] = args.phase
    if args.error:
        updates["error_message"] = args.error
    if args.session_id:
        updates["session_id"] = args.session_id
    if args.pr_url:
        updates["pr_url"] = args.pr_url

    if args.milestones:
        try:
            # Try to parse as JSON string first
            milestones = json.loads(args.milestones)
        except json.JSONDecodeError:
            # Try to read as file
            try:
                with open(args.milestones) as f:
                    milestones = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as exc:
                print(f"Error parsing milestones: {exc}", file=sys.stderr)
                sys.exit(1)
        updates["milestones"] = milestones

    if args.plan:
        # Read from file if it exists, otherwise use as content
        try:
            with open(args.plan) as f:
                updates["plan_document"] = f.read()
        except FileNotFoundError:
            updates["plan_document"] = args.plan

    if args.test_results:
        try:
            updates["test_results"] = json.loads(args.test_results)
        except json.JSONDecodeError:
            try:
                with open(args.test_results) as f:
                    updates["test_results"] = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as exc:
                print(f"Error parsing test results: {exc}", file=sys.stderr)
                sys.exit(1)

    if not updates:
        print("No updates specified", file=sys.stderr)
        sys.exit(1)

    success = update_request(args.request_id, updates)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
