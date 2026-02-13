"""
Manual end-to-end validation for the Batch API.

Usage:
    export BACKEND_TOKEN="<jwt token>"
    python tests/manual/test_batch_e2e.py
"""

from __future__ import annotations

import asyncio
import os

import httpx

BASE_URL = os.getenv("BATCH_BASE_URL", "http://127.0.0.1:8000")
TOKEN = os.getenv("BACKEND_TOKEN")


async def main() -> None:
    if not TOKEN:
        raise SystemExit("Set BACKEND_TOKEN env var to a valid JWT before running this script.")

    headers = {"Authorization": f"Bearer {TOKEN}"}

    async with httpx.AsyncClient(timeout=300) as client:
        print("Submitting batch...")
        submit_resp = await client.post(
            f"{BASE_URL}/api/v1/batch/",
            json={
                "requests": [
                    {"custom_id": "e2e-1", "prompt": "What is 2+2?", "max_tokens": 20},
                    {"custom_id": "e2e-2", "prompt": "What is 3+3?", "max_tokens": 20},
                ],
                "model": "gpt-4o-mini",
                "description": "Batch API E2E verification",
            },
            headers=headers,
        )
        submit_resp.raise_for_status()
        job = submit_resp.json()["data"]
        job_id = job["job_id"]
        print(f"Job ID: {job_id}")

        print("Fetching status...")
        status_resp = await client.get(f"{BASE_URL}/api/v1/batch/{job_id}", headers=headers)
        status_resp.raise_for_status()
        status_data = status_resp.json()["data"]
        print(f"Status: {status_data['status']}")
        print(f"Succeeded: {status_data['succeeded_count']}, Failed: {status_data['failed_count']}")

        print("Downloading results...")
        results_resp = await client.get(f"{BASE_URL}/api/v1/batch/{job_id}/results", headers=headers)
        results_resp.raise_for_status()
        results = results_resp.json()["data"]
        for result in results:
            cid = result["metadata"]["custom_id"]
            print(f"[{cid}] {result['text']}")

        print("Listing most recent batches...")
        list_resp = await client.get(f"{BASE_URL}/api/v1/batch/?limit=5", headers=headers)
        list_resp.raise_for_status()
        listing = list_resp.json()["data"]
        print(f"Total batches returned: {listing['total']}")

        print("Batch E2E test completed.")


if __name__ == "__main__":
    asyncio.run(main())
