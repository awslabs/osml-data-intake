#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

import json
from unittest.mock import AsyncMock, patch

import boto3
import pytest
from moto import mock_aws
from stac_fastapi.types.stac import Item

from aws.osml.data_intake.ingest_processor import handler

mock_message = json.dumps(
    {
        "id": "123",
        "type": "Feature",
        "properties": {"datetime": "2023-01-01T12:00:00Z"},
        "geometry": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
        "links": [
            {"rel": "self", "href": "https://example.com/items/123"},
            {"rel": "collection", "href": "https://example.com/collections/test-collection"},
        ],
        "assets": {"data": {"href": "https://example.com/data.tif", "type": "image/tiff"}},
        "bbox": [-122.4194, 37.7749, -122.4194, 37.7749],
        "stac_version": "1.0.0",
        "stac_extensions": [],
        "collection": "test-collection",
    }
)


def sns_event():
    """
    Constructs a mock SNS event for testing.

    Returns:
        dict: A dictionary representing the SNS event with a predefined message.
    """
    return {"Records": [{"Sns": {"Message": mock_message}}]}


@pytest.fixture
def ingest_env():
    """Set up required AWS resources before each test."""
    with mock_aws():
        sns = boto3.client("sns", region_name="us-east-1")
        sns.create_topic(Name="test-topic")

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")

        yield


class TestIngestProcessor:
    """Test case class for validating the STAC ingestion Lambda functions."""

    def test_handler_success(self, ingest_env):
        """Test the handler function for a successful scenario."""
        with (
            patch(
                "stac_fastapi.opensearch.database_logic.DatabaseLogic.check_collection_exists",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "stac_fastapi.opensearch.database_logic.DatabaseLogic.async_prep_create_item",
                new_callable=AsyncMock,
                return_value=Item(**json.loads(mock_message)),
            ),
            patch(
                "stac_fastapi.opensearch.database_logic.DatabaseLogic.create_item",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            event = sns_event()
            response = handler(event, None)

            assert response["statusCode"] == 200
            assert "successfully" in json.loads(response["body"])

    def test_handler_failure(self, ingest_env):
        """Test the handler function for an unsuccessful scenario."""
        with (
            patch(
                "stac_fastapi.opensearch.database_logic.DatabaseLogic.check_collection_exists",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "stac_fastapi.opensearch.database_logic.DatabaseLogic.async_prep_create_item",
                new_callable=AsyncMock,
                return_value=Item(**json.loads(mock_message)),
            ),
            patch(
                "stac_fastapi.opensearch.database_logic.DatabaseLogic.create_item",
                new_callable=AsyncMock,
                side_effect=Exception("Database error"),
            ),
        ):
            event = sns_event()
            response = handler(event, None)

            assert response["statusCode"] == 500
            assert "Database error" in json.loads(response["body"])["message"]
