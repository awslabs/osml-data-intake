#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from aws.osml.data_intake.managers.sns_manager import SNSManager


@pytest.fixture
def sns_manager():
    """Set up the test environment for SNSManager tests."""
    with mock_aws():
        sns_client = boto3.client("sns", region_name="us-east-1")
        response = sns_client.create_topic(Name="MyTopic")
        sns_topic_arn = response["TopicArn"]
        manager = SNSManager(sns_topic_arn)
        manager.sns_client = sns_client
        yield manager, sns_topic_arn, sns_client


class TestSNSManager:
    """Test suite for the SNSManager class."""

    def test_publish_message_success(self, sns_manager):
        """
        Test successful message publishing.

        Verifies that a message can be successfully published to the SNS topic.
        """
        manager, _, _ = sns_manager
        message = "This is a test message."
        subject = "Test Subject"
        manager.publish_message(message=message, subject=subject)

    def test_publish_message_failure(self, sns_manager):
        """
        Test message publishing failure.

        Simulates a failure scenario by deleting the SNS topic before publishing
        and verifies that a ClientError is raised.
        """
        manager, sns_topic_arn, sns_client = sns_manager
        sns_client.delete_topic(TopicArn=sns_topic_arn)
        message = "This message should fail."
        subject = "Test Subject"

        with pytest.raises(ClientError):
            manager.publish_message(message=message, subject=subject)
