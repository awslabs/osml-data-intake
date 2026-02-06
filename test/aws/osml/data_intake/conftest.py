#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def mock_s3():
    """Mocked S3 resource with a test bucket."""
    with mock_aws():
        s3 = boto3.resource("s3", region_name="us-east-1")
        s3.meta.client.create_bucket(Bucket="test-bucket")
        yield s3


@pytest.fixture
def mock_sns():
    """Mocked SNS client with a test topic."""
    with mock_aws():
        sns = boto3.client("sns", region_name="us-east-1")
        response = sns.create_topic(Name="test-topic")
        yield sns, response["TopicArn"]


@pytest.fixture
def mock_aws_services():
    """Combined S3 + SNS mock environment (single mock_aws context)."""
    with mock_aws():
        s3 = boto3.resource("s3", region_name="us-east-1")
        s3.meta.client.create_bucket(Bucket="test-bucket")

        sns = boto3.client("sns", region_name="us-east-1")
        response = sns.create_topic(Name="test-topic")

        yield {
            "s3": s3,
            "sns": sns,
            "sns_topic_arn": response["TopicArn"],
            "test_bucket": "test-bucket",
        }
