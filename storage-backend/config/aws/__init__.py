"""AWS-specific configuration values."""

from __future__ import annotations

import os
from typing import Dict

from config.environment import ENVIRONMENT

_ENVIRONMENT_DEFAULTS: Dict[str, Dict[str, str]] = {
    "production": {
        "aws_region": "eu-south-2",
        "s3_bucket": "myaiappess3bucket",
        "sqs_queue": "https://sqs.eu-south-2.amazonaws.com/642586419594/ufc-fighters-incoming",
        "sqs_automation_queue": "",
        "sqs_proactive_agent_queue": "",
    },
    "sherlock": {
        "aws_region": "eu-south-2",
        "s3_bucket": "myaiappess3bucketnonprod",
        "sqs_queue": "https://sqs.eu-south-2.amazonaws.com/642586419594/ufc-fighters-incoming",
        "sqs_automation_queue": "",
        "sqs_proactive_agent_queue": "",
    },
    "local": {
        "aws_region": "eu-south-2",
        "s3_bucket": "myaiappess3bucketnonprod",
        "sqs_queue": "https://sqs.eu-south-2.amazonaws.com/642586419594/ufc-fighters-incoming",
        "sqs_automation_queue": "",
        "sqs_proactive_agent_queue": "",
    },
}

_defaults = _ENVIRONMENT_DEFAULTS.get(ENVIRONMENT, _ENVIRONMENT_DEFAULTS["local"])

AWS_REGION = os.getenv("AWS_REGION", _defaults["aws_region"])
IMAGE_S3_BUCKET = os.getenv("IMAGE_S3_BUCKET", _defaults["s3_bucket"])
AWS_SQS_QUEUE_URL = os.getenv("AWS_SQS_QUEUE_URL", _defaults["sqs_queue"])
AWS_SQS_AUTOMATION_QUEUE_URL = os.getenv(
    "AWS_SQS_AUTOMATION_QUEUE_URL", _defaults["sqs_automation_queue"]
)
AWS_SQS_PROACTIVE_AGENT_QUEUE_URL = os.getenv(
    "AWS_SQS_PROACTIVE_AGENT_QUEUE_URL", _defaults["sqs_proactive_agent_queue"]
)

__all__ = [
    "AWS_REGION",
    "IMAGE_S3_BUCKET",
    "AWS_SQS_QUEUE_URL",
    "AWS_SQS_AUTOMATION_QUEUE_URL",
    "AWS_SQS_PROACTIVE_AGENT_QUEUE_URL",
]
