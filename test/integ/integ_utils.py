#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

"""
Shared utilities for integration tests.

This module provides common functions used by both image and GeoJSON integration tests.
"""

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aws.osml.data_intake.utils import logger


@dataclass
class TestConfig:
    """Configuration for integration tests loaded from Lambda environment variables."""

    __test__ = False  # Prevent pytest from treating this as a test class

    input_bucket: str
    input_topic_arn: str
    stac_function_name: str
    stac_root_path: str
    collection_id: str
    max_wait_seconds: int = 300
    wait_interval_seconds: int = 5


def get_config() -> Tuple[Optional[TestConfig], Optional[Dict[str, Any]]]:
    """
    Load test configuration from Lambda environment variables.

    :returns: Tuple of (config, error_response). If config is None, error_response contains the error.
    """
    required_vars = {
        "INPUT_BUCKET": os.environ.get("INPUT_BUCKET"),
        "INPUT_TOPIC_ARN": os.environ.get("INPUT_TOPIC_ARN"),
        "STAC_FUNCTION_NAME": os.environ.get("STAC_FUNCTION_NAME"),
        "STAC_ROOT_PATH": os.environ.get("STAC_ROOT_PATH", "/api/stac"),
    }

    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        return None, create_error_response(f"Missing required environment variables: {missing}")

    config = TestConfig(
        input_bucket=required_vars["INPUT_BUCKET"],
        input_topic_arn=required_vars["INPUT_TOPIC_ARN"],
        stac_function_name=required_vars["STAC_FUNCTION_NAME"],
        stac_root_path=required_vars["STAC_ROOT_PATH"],
        collection_id=os.environ.get("COLLECTION_ID", "integration-test"),
        max_wait_seconds=int(os.environ.get("MAX_WAIT_SECONDS", "300")),
        wait_interval_seconds=int(os.environ.get("WAIT_INTERVAL_SECONDS", "5")),
    )

    return config, None


def create_error_response(error: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Create a standardized error response.

    :param error: The error message.
    :param kwargs: Additional fields to include in the response body.
    :returns: Error response dictionary with statusCode 500.
    """
    body = {"success": False, "error": error, **kwargs}
    return {"statusCode": 500, "body": json.dumps(body)}


def create_success_response(message: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Create a standardized success response.

    :param message: The success message.
    :param kwargs: Additional fields to include in the response body.
    :returns: Success response dictionary with statusCode 200.
    """
    body = {"success": True, "message": message, **kwargs}
    return {"statusCode": 200, "body": json.dumps(body)}


def find_test_file(filename: str) -> Optional[Path]:
    """
    Find a test data file in the expected locations.

    :param filename: The name of the file to find.
    :returns: Path to the file if found, None otherwise.
    """
    # Check Lambda package location first
    lambda_path = Path("/opt/test/data") / filename
    if lambda_path.exists():
        return lambda_path

    # Check local development paths
    local_paths = [
        Path(__file__).parent.parent / "data" / filename,
        Path("test/data") / filename,
    ]

    for path in local_paths:
        if path.exists():
            return path

    return None


def upload_test_file(
    s3_client: Any, bucket: str, s3_key: str, filename: str, tags: Optional[Dict[str, str]] = None
) -> Tuple[bool, Any]:
    """
    Upload a test file to S3.

    :param s3_client: Boto3 S3 client.
    :param bucket: Target S3 bucket name.
    :param s3_key: Target S3 object key.
    :param filename: Name of the test file to upload.
    :param tags: Optional S3 object tags to apply after upload.
    :returns: Tuple of (success, result). On success, result is the S3 URI. On failure, result is the error.
    """
    file_path = find_test_file(filename)
    if not file_path:
        return False, f"Test file not found: {filename}"

    try:
        s3_client.upload_file(str(file_path), bucket, s3_key)
        if tags:
            tag_set = [{"Key": key, "Value": value} for key, value in tags.items()]
            s3_client.put_object_tagging(Bucket=bucket, Key=s3_key, Tagging={"TagSet": tag_set})
        s3_uri = f"s3://{bucket}/{s3_key}"
        logger.info(f"Uploaded test file to {s3_uri}")
        return True, s3_uri
    except Exception as e:
        logger.error(f"Failed to upload test file: {e}")
        return False, e


def publish_to_sns(
    sns_client: Any,
    topic_arn: str,
    s3_uri: str,
    item_id: str,
    collection_id: str,
) -> bool:
    """
    Publish a message to the intake SNS topic.

    :param sns_client: Boto3 SNS client.
    :param topic_arn: SNS topic ARN.
    :param s3_uri: S3 URI of the file to process.
    :param item_id: STAC item ID.
    :param collection_id: STAC collection ID.
    :returns: True if published successfully, False otherwise.
    """
    message = {
        "image_uri": s3_uri,
        "item_id": item_id,
        "collection_id": collection_id,
    }

    try:
        sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message),
            Subject=f"Integration Test: {item_id}",
        )
        logger.info(f"Published message to SNS for item {item_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish to SNS: {e}")
        return False


def create_stac_event(stac_root_path: str, collection_id: str, item_id: str) -> Dict[str, Any]:
    """
    Create an API Gateway v1 event for retrieving a STAC item.

    :param stac_root_path: Base path for STAC API.
    :param collection_id: STAC collection ID.
    :param item_id: STAC item ID.
    :returns: API Gateway event dictionary.
    """
    root_path = stac_root_path.strip("/")
    path = f"/collections/{collection_id}/items/{item_id}"
    full_path = f"/{root_path}{path}" if root_path else path

    return {
        "httpMethod": "GET",
        "path": full_path,
        "pathParameters": {"collection_id": collection_id, "item_id": item_id},
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "headers": {"Content-Type": "application/json", "Accept": "application/json"},
        "multiValueHeaders": {"Content-Type": ["application/json"], "Accept": ["application/json"]},
        "body": None,
        "isBase64Encoded": False,
        "requestContext": {
            "requestId": "integration-test",
            "stage": "default",
            "httpMethod": "GET",
            "path": full_path,
            "requestTime": "01/Jan/2024:00:00:00 +0000",
            "requestTimeEpoch": 1704067200,
            "identity": {"sourceIp": "127.0.0.1", "userAgent": "IntegrationTest/1.0"},
            "apiId": "integration-test-api",
        },
        "resource": full_path,
        "queryString": "",
    }


def parse_lambda_response(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parse a Lambda response payload.

    :param payload: Raw Lambda response payload.
    :returns: Parsed response with statusCode and body, or None if parsing fails.
    """
    if "errorMessage" in payload:
        logger.error(f"Lambda error: {payload.get('errorMessage')}")
        return None

    if "statusCode" not in payload:
        return None

    body_str = payload.get("body")
    if not body_str:
        return {"statusCode": payload["statusCode"], "body": None}

    if isinstance(body_str, dict):
        return {"statusCode": payload["statusCode"], "body": body_str}

    if payload.get("isBase64Encoded", False):
        body_str = base64.b64decode(body_str).decode("utf-8")

    try:
        body = json.loads(body_str)
    except json.JSONDecodeError:
        body = {"raw": body_str}

    return {"statusCode": payload["statusCode"], "body": body}


def _fetch_stac_item(
    lambda_client: Any,
    config: TestConfig,
    collection_id: str,
    item_id: str,
) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    """
    Fetch a single STAC item from the catalog.

    :returns: Tuple of (status_code, body). Returns (None, None) on error.
    """
    try:
        stac_event = create_stac_event(config.stac_root_path, collection_id, item_id)
        response = lambda_client.invoke(
            FunctionName=config.stac_function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(stac_event),
        )

        payload = json.loads(response["Payload"].read())
        parsed = parse_lambda_response(payload)
        if not parsed:
            return None, None

        return parsed["statusCode"], parsed.get("body")
    except Exception as e:
        logger.info(f"Error fetching item {item_id}: {e}")
        return None, None


def _wait_for_items(
    lambda_client: Any, config: TestConfig, collection_id: str, item_ids: List[str]
) -> Tuple[Dict[str, Dict[str, Any]], int, List[str]]:
    """
    Wait for STAC items to appear in the catalog.

    :param lambda_client: Boto3 Lambda client.
    :param config: Test configuration.
    :param collection_id: STAC collection ID.
    :param item_ids: List of STAC item IDs to wait for.
    :returns: Tuple of (found_items_dict, elapsed_seconds, missing_ids).
    """
    remaining = set(item_ids)
    found: Dict[str, Dict[str, Any]] = {}

    logger.info(
        f"Waiting up to {config.max_wait_seconds} seconds for {len(item_ids)} item(s) "
        f"(polling every {config.wait_interval_seconds}s)..."
    )

    elapsed = 0
    while elapsed < config.max_wait_seconds and remaining:
        time.sleep(config.wait_interval_seconds)
        elapsed += config.wait_interval_seconds

        for item_id in list(remaining):
            status_code, body = _fetch_stac_item(lambda_client, config, collection_id, item_id)

            if status_code == 200 and body and body.get("id") == item_id:
                found[item_id] = body
                remaining.remove(item_id)
            elif status_code == 404:
                continue
            elif status_code is not None:
                detail = body.get("detail", "Unknown") if isinstance(body, dict) else "Unknown"
                logger.info(f"Unexpected status {status_code} for {item_id} at {elapsed}s: {detail}")

        if len(item_ids) > 1:
            logger.info(f"Progress at {elapsed}s: found {len(found)}/{len(item_ids)} items")

    return found, elapsed, sorted(remaining)


def wait_and_validate_items(
    lambda_client: Any,
    config: TestConfig,
    collection_id: str,
    item_ids: List[str],
    test_item_id: str,
    s3_client: Any,
    s3_bucket: str,
    s3_key: str,
) -> Dict[str, Any]:
    """
    Poll the STAC catalog until all expected items appear, validate them, and clean up.

    Works for both single-item and multi-item (deconstructed) flows.

    :param lambda_client: Boto3 Lambda client for invoking the STAC API Lambda.
    :param config: ``TestConfig`` containing function names and region.
    :param collection_id: STAC collection to search.
    :param item_ids: List of expected STAC item IDs to wait for.
    :param test_item_id: Identifier used in error reporting and S3 cleanup.
    :param s3_client: Boto3 S3 client for cleanup of test artifacts.
    :param s3_bucket: S3 bucket that holds the uploaded test file.
    :param s3_key: S3 key of the uploaded test file.
    :returns: Response dictionary with ``statusCode``, ``body`` containing
        ``success``, ``items_created``, ``items_validated``, and timing info.
    """
    found_items, elapsed, missing = _wait_for_items(lambda_client, config, collection_id, item_ids)

    if missing:
        return create_error_response(
            f"Items not found in STAC catalog after {elapsed} seconds",
            item_id=test_item_id,
            collection_id=collection_id,
            elapsed_time_seconds=elapsed,
            missing_item_ids=missing,
            items_found=len(found_items),
            items_expected=len(item_ids),
        )

    validation_errors = []
    for item_id in item_ids:
        error = check_stac_item_fields(found_items.get(item_id), item_id, collection_id)
        if error:
            validation_errors.append({"item_id": item_id, "error": error})

    if validation_errors:
        return create_error_response(
            "One or more STAC items failed validation",
            item_id=test_item_id,
            collection_id=collection_id,
            elapsed_time_seconds=elapsed,
            validation_errors=validation_errors,
        )

    try:
        s3_client.delete_object(Bucket=s3_bucket, Key=s3_key)
    except Exception:
        pass

    first_item = found_items.get(item_ids[0])
    return create_success_response(
        "Integration test passed successfully",
        item_id=test_item_id,
        collection_id=collection_id,
        elapsed_time_seconds=elapsed,
        stac_item_id=first_item.get("id") if first_item else None,
        stac_item_type=first_item.get("type") if first_item else None,
        items_created=len(item_ids),
        items_validated=len(item_ids),
    )


def check_stac_item_fields(stac_item: Dict[str, Any], expected_id: str, expected_collection: str) -> Optional[str]:
    """
    Check that a retrieved STAC item contains the expected fields and values.

    This performs lightweight structural validation on items fetched from the
    STAC catalog during integration tests.  It is intentionally separate from
    the source-level ``stac_validator.validate_stac_item`` which performs
    schema-level validation at publish time.

    :param stac_item: The STAC item to check.
    :param expected_id: Expected item ID.
    :param expected_collection: Expected collection ID.
    :returns: Error message if a check fails, None if all checks pass.
    """
    if not stac_item:
        return "STAC item is None"

    if stac_item.get("id") != expected_id:
        return f"Item ID mismatch: expected {expected_id}, got {stac_item.get('id')}"

    if stac_item.get("collection") != expected_collection:
        return f"Collection mismatch: expected {expected_collection}, got {stac_item.get('collection')}"

    if stac_item.get("type") != "Feature":
        return f"Type mismatch: expected 'Feature', got {stac_item.get('type')}"

    required_fields = ["geometry", "bbox", "properties", "assets", "links"]
    missing = [f for f in required_fields if f not in stac_item]
    if missing:
        return f"Missing required fields: {missing}"

    return None
