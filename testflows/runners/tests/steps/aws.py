"""Shared @TestStep(Given) fixtures for AWS-provider tests.

Each step patches boto3 at the Session level so no real API calls are made.
Call from a scenario inside ``with Given("..."):`` to receive the yielded value:

    with Given("mocked EC2 client"):
        ec2 = mock_ec2()
"""
from unittest.mock import MagicMock, patch

from testflows.core import *

from testflows.runners.providers.aws.provider import AWSCloudProvider


@TestStep(Given)
def mock_ec2(self):
    """Patch boto3.Session and yield a mock EC2 client."""
    with patch("boto3.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value = mock_session
        client = MagicMock()
        mock_session.client.return_value = client
        client.describe_subnets.return_value = {
            "Subnets": [
                {"SubnetId": "subnet-12345", "AvailabilityZone": "us-east-1a"},
            ]
        }
        yield client


@TestStep(Given)
def aws_provider(self):
    """Yield (ec2_mock, AWSCloudProvider) with boto3 patched."""
    with Given("mocked EC2 client"):
        ec2 = mock_ec2()
    provider = AWSCloudProvider(
        access_key_id="AKIATEST",
        secret_access_key="secret",
        region="us-east-1",
        security_group="sg-12345",
        subnets=["subnet-12345"],
    )
    yield ec2, provider
