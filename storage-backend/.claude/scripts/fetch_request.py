#!/usr/bin/env python3
"""Fetch automation request details from the database.

This script is used by custom commands to load request context.

Usage:
    python3 fetch_request.py <request_id>
    python3 fetch_request.py <request_id> --field description
    python3 fetch_request.py <request_id> --format json
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


def fetch_request(request_id: str) -> dict | None:
    """Fetch request from the API."""
    base_url = get_api_base()
    url = urljoin(base_url, f"/api/v1/automation/requests/{request_id}")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("data", data)
    except requests.RequestException as exc:
        print(f"Error fetching request: {exc}", file=sys.stderr)
        return None


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Fetch automation request details")
    parser.add_argument("request_id", help="Request ID to fetch")
    parser.add_argument("--field", help="Specific field to extract")
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format",
    )

    args = parser.parse_args()

    request = fetch_request(args.request_id)

    if request is None:
        print(f"Request {args.request_id} not found", file=sys.stderr)
        sys.exit(1)

    if args.field:
        value = request.get(args.field)
        if value is None:
            print(f"Field '{args.field}' not found in request", file=sys.stderr)
            sys.exit(1)
        if isinstance(value, (dict, list)):
            print(json.dumps(value, indent=2))
        else:
            print(value)
    elif args.format == "json":
        print(json.dumps(request, indent=2))
    else:
        # Human-readable text format
        print(f"Request ID: {request.get('id')}")
        print(f"Type: {request.get('type')}")
        print(f"Status: {request.get('status')}")
        print(f"Priority: {request.get('priority')}")
        print(f"Title: {request.get('title')}")
        print(f"Created: {request.get('created_at')}")
        print()
        print("Description:")
        print("-" * 40)
        print(request.get("description", ""))
        print("-" * 40)

        if request.get("attachments"):
            print()
            print(f"Attachments: {len(request['attachments'])} items")

        if request.get("milestones"):
            print()
            print("Milestones:")
            for m in request["milestones"]:
                status_icon = "+" if m.get("status") == "completed" else "-"
                print(f"  [{status_icon}] {m.get('id')}: {m.get('title')}")


if __name__ == "__main__":
    main()
