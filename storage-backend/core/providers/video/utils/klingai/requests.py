"""HTTP client for KlingAI API."""

import asyncio
import time
from typing import Dict, Any, Optional, List

import httpx

from core.exceptions import ProviderError, ConfigurationError
from .auth import KlingAIAuth
from .models import TaskStatus, TaskResponse


class KlingAIClient:
    """HTTP client for KlingAI API requests."""

    def __init__(
        self,
        auth: KlingAIAuth,
        base_url: str = "https://api-singapore.klingai.com",
        timeout: float = 300.0,
        poll_interval: float = 5.0,
    ):
        """
        Initialize KlingAI API client.

        Args:
            auth: KlingAI authentication handler
            base_url: API base URL
            timeout: Request timeout in seconds
            poll_interval: Status polling interval in seconds
        """
        self.auth = auth
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> TaskResponse:
        """
        Make HTTP request to KlingAI API.

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint (e.g., "/v1/videos/text2video")
            json_data: Request body (for POST)

        Returns:
            Parsed TaskResponse

        Raises:
            ProviderError: On HTTP errors or invalid responses
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            **self.auth.get_auth_header()
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method == "GET":
                    response = await client.get(url, headers=headers)
                elif method == "POST":
                    response = await client.post(url, headers=headers, json=json_data)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                data = response.json()

                return TaskResponse(**data)

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if hasattr(e.response, "text") else str(e)
            raise ProviderError(
                f"KlingAI API error ({e.response.status_code}): {error_detail}"
            ) from e
        except httpx.RequestError as e:
            raise ProviderError(f"KlingAI request failed: {str(e)}") from e
        except Exception as e:
            raise ProviderError(f"Unexpected error: {str(e)}") from e

    async def create_task(
        self,
        endpoint: str,
        payload: Dict[str, Any]
    ) -> str:
        """
        Create a video generation task.

        Args:
            endpoint: Creation endpoint (e.g., "/v1/videos/text2video")
            payload: Request payload

        Returns:
            Task ID

        Raises:
            ProviderError: On API errors
        """
        response = await self._make_request("POST", endpoint, payload)

        if response.code != 0:
            raise ProviderError(
                f"Task creation failed: {response.message} (code: {response.code})"
            )

        task_id = response.data.get("task_id")
        if not task_id:
            raise ProviderError("No task_id in response")

        return task_id

    async def get_task_status(
        self,
        endpoint: str,
        task_id: str
    ) -> Dict[str, Any]:
        """
        Get task status.

        Args:
            endpoint: Query endpoint (e.g., "/v1/videos/text2video")
            task_id: Task ID

        Returns:
            Task data dictionary

        Raises:
            ProviderError: On API errors
        """
        query_endpoint = f"{endpoint}/{task_id}"
        response = await self._make_request("GET", query_endpoint)

        if response.code != 0:
            raise ProviderError(
                f"Status query failed: {response.message} (code: {response.code})"
            )

        return response.data

    async def poll_until_complete(
        self,
        endpoint: str,
        task_id: str,
        timeout: Optional[float] = None,
        poll_interval: Optional[float] = None,
        runtime: Any = None,
    ) -> Dict[str, Any]:
        """
        Poll task status until completion.

        Args:
            endpoint: Query endpoint
            task_id: Task ID
            timeout: Max wait time in seconds (default: self.timeout)
            poll_interval: Polling interval in seconds (default: self.poll_interval)

        Returns:
            Task result dictionary

        Raises:
            ProviderError: On task failure or timeout
        """
        timeout = timeout or self.timeout
        poll_interval = poll_interval or self.poll_interval
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            # Check for cancellation
            if runtime and runtime.is_cancelled():
                logger.info("KlingAI video cancelled (task=%s)", task_id)
                raise asyncio.CancelledError("Video generation cancelled by user")

            task_data = await self.get_task_status(endpoint, task_id)
            status = task_data.get("task_status")

            if status == TaskStatus.SUCCEED.value:
                task_result = task_data.get("task_result")
                if not task_result:
                    raise ProviderError("No task_result in successful response")
                return task_result

            elif status == TaskStatus.FAILED.value:
                error_msg = task_data.get("task_status_msg", "Unknown error")
                raise ProviderError(f"Task failed: {error_msg}")

            elif status in [TaskStatus.SUBMITTED.value, TaskStatus.PROCESSING.value]:
                await asyncio.sleep(poll_interval)

            else:
                raise ProviderError(f"Unknown task status: {status}")

        raise ProviderError(f"Task timeout after {timeout}s")

    async def download_video(self, video_url: str) -> bytes:
        """
        Download video from URL.

        Args:
            video_url: Video URL from KlingAI

        Returns:
            Video bytes

        Raises:
            ProviderError: On download errors
        """
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(video_url)
                response.raise_for_status()
                return response.content

        except httpx.HTTPStatusError as e:
            raise ProviderError(
                f"Video download failed ({e.response.status_code}): {e}"
            ) from e
        except Exception as e:
            raise ProviderError(f"Video download error: {str(e)}") from e
