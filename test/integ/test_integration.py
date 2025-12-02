#  Copyright 2024-2025 Amazon.com, Inc. or its affiliates.

"""
Integration test for the data catalog Lambda function.

This test invokes the data-catalog-integration-test Lambda function
which runs a smoke test that:
1. Uploads a test image to S3
2. Publishes to the intake SNS topic
3. Waits for processing
4. Retrieves the item from the STAC catalog
5. Validates it was added correctly

Can be configured via environment variables:
- INTEG_TEST_LAMBDA_FUNCTION_NAME: Lambda function name (default: data-catalog-integration-test)
- INTEG_TEST_LAMBDA_REGION: AWS region (default: us-west-2)

Usage:
    pytest test/integ/test_integration.py -s  # Use -s to see print output
    pytest test/integ/test_integration.py::test_integration -v -s
    INTEG_TEST_LAMBDA_FUNCTION_NAME=my-function pytest test/integ/test_integration.py -s
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
) -> Dict[str, Any]:
    """
    Invoke the integration test Lambda function.

    :param lambda_function_name: Name of the Lambda function to invoke
    :param lambda_region: AWS region for Lambda invocation
    :return: Response from the Lambda function with statusCode and body
    """
    config = Config(
        read_timeout=LAMBDA_TIMEOUT_SECONDS,
        retries={"max_attempts": 0},  # Don't retry, let the function handle its own retries
    )
    lambda_client = boto3.client("lambda", region_name=lambda_region, config=config)

    # The integration test handler doesn't require any event payload
    # It reads all configuration from environment variables
    event: Dict[str, Any] = {}

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


@pytest.mark.integration
def test_integration():
    """
    Pytest test function to run the integration test.

    This test is marked with @pytest.mark.integration and is excluded from
    default test runs (e.g., tox). To run it explicitly:

        pytest -m integration
        pytest test/integ/test_integration.py
    """
    lambda_function_name = os.environ.get("INTEG_TEST_LAMBDA_FUNCTION_NAME", DEFAULT_LAMBDA_FUNCTION_NAME)
    lambda_region = os.environ.get("INTEG_TEST_LAMBDA_REGION", DEFAULT_LAMBDA_REGION)

    start_time = time.time()
    result = invoke_integration_test(
        lambda_function_name=lambda_function_name,
        lambda_region=lambda_region,
    )
    elapsed_time = time.time() - start_time

    # Log timing information
    print(f"\nLambda invocation took {elapsed_time:.2f} seconds")

    # Assert test passed
    status_code = result.get("statusCode")
    assert status_code == 200, f"Expected status 200, got {status_code}"

    body = result.get("body", {})
    if not isinstance(body, dict):
        body = _parse_json_body(body)

    # Verify the Lambda actually did work by checking for elapsed_time_seconds in response
    if "elapsed_time_seconds" in body:
        lambda_elapsed = body.get("elapsed_time_seconds", 0)
        print(f"Lambda reported elapsed time: {lambda_elapsed} seconds")
        # The Lambda should take at least a few seconds for the full workflow
        assert lambda_elapsed > 0, "Lambda should report elapsed time > 0"

    assert body.get("success") is True, f"Test failed: {body.get('error', 'Unknown error')}"
