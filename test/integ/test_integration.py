#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

"""
Integration tests for the data catalog Lambda function.

Each test invokes the ``data-catalog-integration-test`` Lambda which:
1. Uploads a test file (image or GeoJSON) to S3
2. Publishes to the intake SNS topic
3. Waits for processing
4. Retrieves the resulting STAC item(s) from the catalog
5. Validates they were created correctly

Three test flows are included:
- **image** -- processes a TIFF image and produces one STAC item.
- **geojson** -- processes a GeoJSON FeatureCollection as a single STAC item.
- **geojson_decomposed** -- processes a GeoJSON FeatureCollection with the
  ``DECONSTRUCT_FEATURE_COLLECTIONS`` S3 tag, producing one STAC item per feature.

Can be configured via environment variables:
- INTEG_TEST_LAMBDA_FUNCTION_NAME: Lambda function name (default: data-catalog-integration-test)
- INTEG_TEST_LAMBDA_REGION: AWS region (default: us-west-2)

Usage:
    pytest test/integ/test_integration.py -s -m integration
    INTEG_TEST_LAMBDA_FUNCTION_NAME=my-function pytest test/integ/test_integration.py -s -m integration
"""

import json
import os
import time
from typing import Any, Dict

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError

# Constants
DEFAULT_LAMBDA_FUNCTION_NAME = "data-catalog-integration-test"
DEFAULT_LAMBDA_REGION = "us-west-2"
LAMBDA_TIMEOUT_SECONDS = 600  # 10 minutes


def _parse_json_body(body: Any) -> Dict[str, Any]:
    """Parse JSON body, handling both string and dict inputs."""
    if isinstance(body, str):
        return json.loads(body)
    return body if isinstance(body, dict) else {}


def invoke_integration_test(
    lambda_function_name: str = DEFAULT_LAMBDA_FUNCTION_NAME,
    lambda_region: str = DEFAULT_LAMBDA_REGION,
    test_type: str | None = None,
) -> Dict[str, Any]:
    """
    Invoke the integration test Lambda function.

    :param lambda_function_name: Name of the Lambda function to invoke.
    :param lambda_region: AWS region for Lambda invocation.
    :param test_type: Which test flow to run -- ``None`` for image,
        ``"geojson"`` for single-item GeoJSON, or ``"geojson_decomposed"``
        for per-feature decomposition.
    :returns: Response dictionary with ``statusCode`` and ``body`` keys.
    """
    config = Config(
        read_timeout=LAMBDA_TIMEOUT_SECONDS,
        retries={"max_attempts": 0},  # Don't retry, let the function handle its own retries
    )
    lambda_client = boto3.client("lambda", region_name=lambda_region, config=config)

    # The integration test handler reads configuration from environment variables.
    # We can optionally control which flow to run by passing 'test_type' in the event.
    event: Dict[str, Any] = {"test_type": test_type} if test_type else {}

    try:
        print(f"Invoking integration test Lambda function: {lambda_function_name}")
        print(f"Region: {lambda_region}")
        print("=" * 60)

        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        payload = json.loads(response["Payload"].read())

        # Check for Lambda errors
        if "errorMessage" in payload or "errorType" in payload:
            error_msg = payload.get("errorMessage", str(payload))
            error_type = payload.get("errorType", "UnknownError")
            raise Exception(f"Lambda invocation failed ({error_type}): {error_msg}")

        # Parse the response
        if "statusCode" in payload:
            body = _parse_json_body(payload.get("body", "{}"))
            return {
                "statusCode": payload["statusCode"],
                "body": body,
            }

        return payload

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        raise Exception(f"Failed to invoke Lambda function ({error_code}): {error_message}") from e


def _run_integration_test(test_type: str | None = None) -> Dict[str, Any]:
    """
    Invoke the integration test Lambda, assert success, and return the parsed body.

    :param test_type: Which test flow to run (None for image, "geojson", "geojson_decomposed").
    :returns: Parsed response body dictionary.
    """
    label = test_type or "image"
    lambda_function_name = os.environ.get("INTEG_TEST_LAMBDA_FUNCTION_NAME", DEFAULT_LAMBDA_FUNCTION_NAME)
    lambda_region = os.environ.get("INTEG_TEST_LAMBDA_REGION", DEFAULT_LAMBDA_REGION)

    print(f"\n=== Running integration test: {label} ===")
    start_time = time.time()
    result = invoke_integration_test(
        lambda_function_name=lambda_function_name,
        lambda_region=lambda_region,
        test_type=test_type,
    )
    elapsed_time = time.time() - start_time
    print(f"\n{label} Lambda invocation took {elapsed_time:.2f} seconds")

    status_code = result.get("statusCode")
    assert status_code == 200, f"Expected status 200, got {status_code}"

    body = result.get("body", {})
    if not isinstance(body, dict):
        body = _parse_json_body(body)

    assert body.get("success") is True, f"{label} test failed: {body.get('error', 'Unknown error')}"

    return body


@pytest.mark.integration
def test_integration_image():
    """
    Image processing integration test.

    Uploads a test TIFF image, triggers the intake pipeline, and validates
    that the resulting STAC item appears in the catalog.
    """
    body = _run_integration_test()

    if "elapsed_time_seconds" in body:
        lambda_elapsed = body["elapsed_time_seconds"]
        print(f"Lambda reported elapsed time: {lambda_elapsed} seconds")
        assert lambda_elapsed > 0, "Lambda should report elapsed time > 0"


@pytest.mark.integration
def test_integration_geojson():
    """
    GeoJSON single-item integration test.

    Uploads a GeoJSON FeatureCollection and validates that the processor
    creates exactly one STAC item for the entire file (default mode).
    """
    body = _run_integration_test(test_type="geojson")

    assert body.get("items_created") == 1
    assert body.get("items_validated") == 1


@pytest.mark.integration
def test_integration_geojson_decomposed():
    """
    GeoJSON decomposition integration test.

    Uploads a GeoJSON FeatureCollection with an S3 tag override and validates
    that the processor creates one STAC item per feature (31 items).
    """
    body = _run_integration_test(test_type="geojson_decomposed")

    assert body.get("items_created") == 31
    assert body.get("items_validated") == 31
