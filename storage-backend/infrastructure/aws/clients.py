"""Initialise AWS service clients used by the infrastructure layer."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

import boto3
from botocore.config import Config as BotoConfig

from config.api_keys import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

logger = logging.getLogger(__name__)

_access_key = os.getenv("AWS_ACCESS_KEY_ID")
_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

def _get_region() -> str:
    """Get AWS region, importing lazily to avoid circular imports."""
    from config.api_keys import AWS_REGION
    return AWS_REGION

_region = _get_region()

_boto_config = BotoConfig(
    region_name=_region,
    retries={"max_attempts": 3, "mode": "standard"},
    connect_timeout=10,
    read_timeout=30,
)

aws_clients: Dict[str, Any] = {}


def _build_client(service_name: str) -> Any:
    """Return a boto3 client for ``service_name`` using static credentials."""

    return boto3.client(
        service_name,
        aws_access_key_id=_access_key or None,
        aws_secret_access_key=_secret_key or None,
        config=_boto_config,
    )


try:
    if _access_key and _secret_key:
        aws_clients["s3"] = _build_client("s3")
        aws_clients["sqs"] = _build_client("sqs")
        logger.info("Initialised AWS clients (S3, SQS)")
    else:
        logger.warning("AWS credentials not found, AWS clients not initialised")
except Exception as exc:  # pragma: no cover - rely on boto3 for correctness
    logger.error("Error initialising AWS clients: %s", exc)
    raise


def get_s3_client() -> Any:
    """Return the cached S3 client or ``None`` when unavailable."""

    return aws_clients.get("s3")


def get_sqs_client() -> Any:
    """Return the cached SQS client or ``None`` when unavailable."""

    return aws_clients.get("sqs")


__all__ = ["aws_clients", "get_s3_client", "get_sqs_client"]
