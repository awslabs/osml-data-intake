#  Copyright 2024-2025 Amazon.com, Inc. or its affiliates.

import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from aws.osml.data_intake.utils import logger


@dataclass
class TestConfig:
    """Configuration for integration test."""

    input_bucket: str
    input_topic_arn: str
    stac_function_name: str
    stac_root_path: str
    collection_id: str
    max_wait_seconds: int
    wait_interval_seconds: int


def _create_error_response(error: str, **kwargs) -> Dict[str, Any]:
    """Create a standardized error response."""
    return {"statusCode": 500, "body": json.dumps({"success": False, "error": error, **kwargs})}


def _create_success_response(message: str, **kwargs) -> Dict[str, Any]:
    """Create a standardized success response."""
    return {"statusCode": 200, "body": json.dumps({"success": True, "message": message, **kwargs})}


def _get_config() -> Tuple[Optional[TestConfig], Optional[Dict[str, Any]]]:
    """Get configuration from environment variables."""
    input_bucket = os.environ.get("INPUT_BUCKET")
    input_topic_arn = os.environ.get("INPUT_TOPIC_ARN")

    if not input_bucket or not input_topic_arn:
        return None, _create_error_response("Missing required environment variables: INPUT_BUCKET and INPUT_TOPIC_ARN")

    return (
        TestConfig(
            input_bucket=input_bucket,
            input_topic_arn=input_topic_arn,
            stac_function_name=os.environ.get("STAC_FUNCTION_NAME", "data-catalog-stac"),
            stac_root_path=os.environ.get("STAC_ROOT_PATH", "data-catalog"),
            collection_id=os.environ.get("COLLECTION_ID", "OSML"),
            max_wait_seconds=int(os.environ.get("MAX_WAIT_SECONDS", "60")),
            wait_interval_seconds=int(os.environ.get("WAIT_INTERVAL_SECONDS", "5")),
        ),
        None,
    )


def _find_test_image() -> Optional[str]:
    """Find the test image file path."""
    # Try relative path first (for local development)
    test_image_path = os.path.join(os.path.dirname(__file__), "..", "data", "small.tif")
    if os.path.exists(test_image_path):
        return test_image_path

    # Try Docker path
    test_image_path = "/opt/test/data/small.tif"
    if os.path.exists(test_image_path):
        return test_image_path

    return None


def _upload_test_image(s3_client: Any, bucket: str, s3_key: str) -> Tuple[bool, Optional[str]]:
    """Upload test image to S3."""
    test_image_path = _find_test_image()
    if not test_image_path:
        return False, "Test image not found. Tried relative and /opt/test/data/small.tif"

    test_image_s3_uri = f"s3://{bucket}/{s3_key}"
    logger.info(f"Uploading test image to {test_image_s3_uri}")

    try:
        with open(test_image_path, "rb") as f:
            s3_client.upload_fileobj(f, bucket, s3_key)
        logger.info(f"Successfully uploaded test image to {test_image_s3_uri}")
        return True, test_image_s3_uri
    except Exception as e:
        return False, f"Failed to upload test image: {e}"


def _publish_to_sns(sns_client: Any, topic_arn: str, image_uri: str, item_id: str, collection_id: str) -> bool:
    """Publish message to SNS topic."""
    message = {"image_uri": image_uri, "item_id": item_id, "collection_id": collection_id}

    logger.info(f"Publishing message to {topic_arn}: {json.dumps(message)}")
    try:
        response = sns_client.publish(TopicArn=topic_arn, Message=json.dumps(message))
        logger.info(f"Message published with MessageId: {response['MessageId']}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish to SNS: {e}")
        return False


def _create_stac_event(stac_root_path: str, collection_id: str, item_id: str) -> Dict[str, Any]:
    """Create API Gateway v1 event for STAC function (Mangum-compatible format)."""
    full_path = f"/{stac_root_path}/collections/{collection_id}/items/{item_id}"
    current_time = int(time.time())

    return {
        "httpMethod": "GET",
        "path": full_path,
        "pathParameters": {"collection_id": collection_id, "item_id": item_id},
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "headers": {"Content-Type": "application/json", "Accept": "application/json"},
        "multiValueHeaders": {
            "Content-Type": ["application/json"],
            "Accept": ["application/json"],
        },
        "body": None,
        "isBase64Encoded": False,
        "requestContext": {
            "requestId": f"integration-test-{current_time}",
            "stage": "default",
            "httpMethod": "GET",
            "path": full_path,
            "requestTime": "01/Jan/2024:00:00:00 +0000",
            "requestTimeEpoch": current_time,
            "identity": {"sourceIp": "127.0.0.1", "userAgent": "IntegrationTest/1.0"},
            "apiId": "integration-test-api",
        },
        "resource": full_path,
        "queryString": "",
    }


def _parse_lambda_response(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse Lambda response payload and extract JSON body."""
    # Check for Lambda errors
    if "errorMessage" in payload or "errorType" in payload:
        error_msg = payload.get("errorMessage", str(payload))
        logger.warning(f"Lambda invocation error: {error_msg}")
        return None

    # Check if we have a status code (API Gateway response format)
    if "statusCode" not in payload:
        logger.warning(f"Unexpected response format: {payload}")
        return None

    status_code = payload.get("statusCode")
    body_str = payload.get("body")

    # Handle empty or missing body
    if not body_str:
        if status_code == 404:
            return {"statusCode": 404, "body": None}
        logger.warning(f"Empty response body with status {status_code}")
        return None

    # Handle dict body (already parsed)
    if isinstance(body_str, dict):
        return {"statusCode": status_code, "body": body_str}

    # Handle string body - may need base64 decoding
    if not isinstance(body_str, str) or not body_str.strip():
        logger.warning(f"Invalid response body format: {type(body_str)}")
        return None

    # Try base64 decoding if needed (Mangum may encode responses)
    if payload.get("isBase64Encoded", False):
        try:
            body_str = base64.b64decode(body_str).decode("utf-8")
        except Exception as e:
            logger.warning(f"Failed to decode base64 body: {e}")
            return None
    else:
        # Try auto-detecting base64 (Mangum sometimes encodes without flag)
        try:
            if len(body_str) > 20 and all(
                c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for c in body_str
            ):
                decoded = base64.b64decode(body_str).decode("utf-8")
                if decoded.strip().startswith(("{", "[")):
                    body_str = decoded
        except Exception:
            pass

    # Parse JSON body
    try:
        body = json.loads(body_str)
        return {"statusCode": status_code, "body": body}
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON body: {e}, body: {body_str[:200]}")
        return None


def _wait_for_item(lambda_client: Any, config: TestConfig, item_id: str) -> Tuple[bool, Optional[Dict[str, Any]], int]:
    """Wait for item to appear in STAC catalog."""
    logger.info(f"Waiting up to {config.max_wait_seconds} seconds for item to be processed...")

    elapsed_time = 0
    while elapsed_time < config.max_wait_seconds:
        time.sleep(config.wait_interval_seconds)
        elapsed_time += config.wait_interval_seconds

        try:
            stac_event = _create_stac_event(config.stac_root_path, config.collection_id, item_id)
            response = lambda_client.invoke(
                FunctionName=config.stac_function_name, InvocationType="RequestResponse", Payload=json.dumps(stac_event)
            )

            payload = json.loads(response["Payload"].read())
            parsed = _parse_lambda_response(payload)

            if not parsed:
                continue

            status_code = parsed["statusCode"]
            body = parsed.get("body")

            if status_code == 200 and body and body.get("id") == item_id:
                logger.info(f"Item found in STAC catalog after {elapsed_time} seconds")
                return True, body, elapsed_time
            elif status_code == 404:
                logger.info(f"Item not found yet (status 404 at {elapsed_time}s)")
            else:
                error_detail = body.get("detail", "Unknown error") if body else "Unknown error"
                logger.info(f"Unexpected status {status_code} at {elapsed_time}s: {error_detail}")

        except ClientError as e:
            logger.info(f"Item not found yet (attempt at {elapsed_time}s): {e}")
        except Exception as e:
            logger.warning(f"Error retrieving item: {e}")

    return False, None, elapsed_time


def _validate_stac_item(stac_item: Dict[str, Any], item_id: str, collection_id: str) -> Optional[str]:
    """Validate STAC item structure and content."""
    # Check required fields
    required_fields = ["id", "type", "collection", "assets"]
    missing_fields = [field for field in required_fields if field not in stac_item]
    if missing_fields:
        return f"STAC item missing required fields: {missing_fields}"

    # Validate item ID matches
    if stac_item.get("id") != item_id:
        return f"STAC item ID mismatch: expected {item_id}, got {stac_item.get('id')}"

    # Validate collection ID matches
    if stac_item.get("collection") != collection_id:
        return f"STAC item collection mismatch: expected {collection_id}, got {stac_item.get('collection')}"

    return None


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Integration test Lambda handler that:
    1. Uploads a test image to S3
    2. Publishes to the intake SNS topic
    3. Waits for processing
    4. Retrieves the item from the STAC catalog
    5. Validates it was added correctly

    :param event: The event payload containing test configuration.
    :param context: The Lambda execution context.
    :return: Test result with success/failure status.
    """
    try:
        # Get configuration
        config, error_response = _get_config()
        if error_response:
            return error_response

        # Generate unique test item ID
        test_item_id = f"integration-test-{int(time.time())}"
        logger.info(f"Starting integration test with item_id: {test_item_id}")

        # Step 1: Upload test image to S3
        s3_client = boto3.client("s3")
        s3_key = f"integration-tests/{test_item_id}/small.tif"

        success, result = _upload_test_image(s3_client, config.input_bucket, s3_key)
        if not success:
            return _create_error_response(result, item_id=test_item_id)

        test_image_s3_uri = result

        # Step 2: Publish to intake SNS topic
        sns_client = boto3.client("sns")
        if not _publish_to_sns(sns_client, config.input_topic_arn, test_image_s3_uri, test_item_id, config.collection_id):
            return _create_error_response(
                "Failed to publish message to SNS", item_id=test_item_id, collection_id=config.collection_id
            )

        # Step 3: Wait for processing and retrieve from STAC catalog
        lambda_client = boto3.client("lambda")
        item_found, stac_item, elapsed_time = _wait_for_item(lambda_client, config, test_item_id)

        # Step 4: Validate results
        if not item_found:
            return _create_error_response(
                f"Item {test_item_id} not found in STAC catalog after {elapsed_time} seconds",
                item_id=test_item_id,
                collection_id=config.collection_id,
            )

        validation_error = _validate_stac_item(stac_item, test_item_id, config.collection_id)
        if validation_error:
            return _create_error_response(validation_error, item_id=test_item_id, stac_item=stac_item)

        # Cleanup: Delete test image from S3
        try:
            s3_client.delete_object(Bucket=config.input_bucket, Key=s3_key)
            logger.info(f"Cleaned up test image: {s3_key}")
        except Exception as e:
            logger.warning(f"Failed to cleanup test image: {e}")

        # Return success
        return _create_success_response(
            "Integration test passed successfully",
            item_id=test_item_id,
            collection_id=config.collection_id,
            elapsed_time_seconds=elapsed_time,
            stac_item_id=stac_item.get("id"),
            stac_item_type=stac_item.get("type"),
        )

    except Exception as e:
        logger.error(f"Integration test failed: {e}", exc_info=True)
        return _create_error_response(str(e))
