#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

import json
import time
from typing import Any, Dict, List, Union

import boto3

from aws.osml.data_intake.geojson_processor import generate_deterministic_id

from .integ_utils import (
    TestConfig,
    create_error_response,
    find_test_file,
    publish_to_sns,
    upload_test_file,
    wait_and_validate_items,
)


def run_geojson_test(config: TestConfig, deconstruct: bool = False) -> Dict[str, Any]:
    """Execute the GeoJSON end-to-end integration test."""
    test_name = "decomposed" if deconstruct else "single"
    test_item_id = f"integration-geojson-{test_name}-test-{int(time.time())}"
    geojson_collection_id = f"{config.collection_id}-geojson"

    s3_client = boto3.client("s3")
    s3_key = f"integration-tests/{test_item_id}/feature_collection.geojson"
    tags = {"DECONSTRUCT_FEATURE_COLLECTIONS": "true"} if deconstruct else None
    success, result = upload_test_file(s3_client, config.input_bucket, s3_key, "feature_collection.geojson", tags=tags)
    if not success:
        return create_error_response(str(result), item_id=test_item_id)

    if deconstruct:
        item_ids = _get_expected_decomposed_ids(geojson_collection_id, s3_key, test_item_id)
        if isinstance(item_ids, dict):
            return item_ids
    else:
        item_ids = [test_item_id]

    sns_client = boto3.client("sns")
    if not publish_to_sns(sns_client, config.input_topic_arn, result, test_item_id, geojson_collection_id):
        return create_error_response(
            "Failed to publish message to SNS", item_id=test_item_id, collection_id=geojson_collection_id
        )

    lambda_client = boto3.client("lambda")
    return wait_and_validate_items(
        lambda_client,
        config,
        geojson_collection_id,
        item_ids,
        test_item_id,
        s3_client,
        config.input_bucket,
        s3_key,
    )


def _get_expected_decomposed_ids(collection_id: str, s3_key: str, test_item_id: str) -> Union[List[str], Dict[str, Any]]:
    """Read local GeoJSON and generate expected deterministic IDs."""
    geojson_path = find_test_file("feature_collection.geojson")
    if not geojson_path:
        return create_error_response("Test file not found: feature_collection.geojson", item_id=test_item_id)

    with open(geojson_path, "r", encoding="utf-8") as f:
        geojson_data = json.load(f)

    features = geojson_data.get("features", []) or []
    if not features:
        return create_error_response("FeatureCollection contains no features", item_id=test_item_id)

    return [generate_deterministic_id(feature, collection_id, s3_key) for feature in features]
