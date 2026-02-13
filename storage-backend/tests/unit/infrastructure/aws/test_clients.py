"""Tests for AWS client initialisation module."""

import importlib
import sys


def reload_module():
    if "infrastructure.aws.clients" in sys.modules:
        del sys.modules["infrastructure.aws.clients"]
    return importlib.import_module("infrastructure.aws.clients")


def test_aws_clients_without_credentials(monkeypatch):
    """Without credentials, no AWS clients should be initialised."""

    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    module = reload_module()
    assert module.aws_clients == {}


def test_aws_clients_with_credentials(monkeypatch):
    """Providing credentials should set up S3 and SQS clients."""

    import boto3

    class DummyBotoClient:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: DummyBotoClient())

    module = reload_module()
    assert {"s3", "sqs"}.issubset(module.aws_clients.keys())
