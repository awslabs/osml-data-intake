#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

import time
from typing import Any, Dict

import boto3

from .integ_utils import (
    TestConfig,
    create_error_response,
    publish_to_sns,
    upload_test_file,
    wait_and_validate_items,
)


def run_image_test(config: TestConfig) -> Dict[str, Any]:
    """Execute the image end-to-end integration test."""
    test_item_id = f"integration-test-{int(time.time())}"

    s3_client = boto3.client("s3")
    s3_key = f"integration-tests/{test_item_id}/small.tif"
    success, result = upload_test_file(s3_client, config.input_bucket, s3_key, "small.tif")
    if not success:
        return create_error_response(str(result), item_id=test_item_id)

    test_image_s3_uri = result

    sns_client = boto3.client("sns")
    if not publish_to_sns(sns_client, config.input_topic_arn, test_image_s3_uri, test_item_id, config.collection_id):
        return create_error_response(
            "Failed to publish message to SNS", item_id=test_item_id, collection_id=config.collection_id
        )

    lambda_client = boto3.client("lambda")
    return wait_and_validate_items(
        lambda_client,
        config,
        config.collection_id,
        [test_item_id],
        test_item_id,
        s3_client,
        config.input_bucket,
        s3_key,
    )
