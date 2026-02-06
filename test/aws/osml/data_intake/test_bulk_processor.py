# Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

import json
import os
from unittest.mock import MagicMock, mock_open, patch

import boto3
import pytest
from moto import mock_aws

from aws.osml.data_intake.bulk_processor import BulkProcessor, process_manifest_file
from aws.osml.data_intake.managers import S3Url


@pytest.fixture
def bulk_env():
    """Set up the test environment for BulkProcessor tests."""
    with mock_aws():
        test_bucket = "test-bucket"
        aws_s3 = boto3.resource("s3", region_name="us-east-1")
        aws_s3.meta.client.create_bucket(Bucket=test_bucket)
        aws_s3.meta.client.upload_file("./test/data/small.tif", test_bucket, "small.tif")
        aws_s3.meta.client.upload_file("./test/data/manifest.json", test_bucket, "manifest.json")

        s3_uri = os.environ["S3_URI"]
        input_path = os.environ["S3_INPUT_PATH"]
        output_path = os.environ["S3_OUTPUT_PATH"]
        output_bucket = os.environ["S3_OUTPUT_BUCKET"]
        stac_endpoint = os.environ["STAC_ENDPOINT"]
        collection_id = os.environ["COLLECTION_ID"]
        bulk_processor = BulkProcessor(aws_s3, output_path, output_bucket, stac_endpoint, collection_id, input_path)

        test_image = f"s3://{test_bucket}/small.tif"
        error_details = {"image": test_image, "error": "TEST_ERROR", "internal_traceback": "TEST_TRACEBACK"}
        stac_items = [
            {
                "id": "123",
                "type": "Feature",
                "properties": {},
                "geometry": {},
                "links": [],
                "assets": {},
                "bbox": [],
                "stac_version": "1.0.0",
                "stac_extensions": [],
                "collection": "test-collection",
            }
        ]

        yield {
            "aws_s3": aws_s3,
            "bulk_processor": bulk_processor,
            "test_bucket": test_bucket,
            "test_image": test_image,
            "s3_uri": s3_uri,
            "input_path": input_path,
            "error_details": error_details,
            "stac_items": stac_items,
        }


class TestBulkProcessor:
    def test_process_manifest_file(self, bulk_env):
        lst = process_manifest_file(bulk_env["aws_s3"], bulk_env["input_path"], bulk_env["s3_uri"])

        assert len(lst) == 1
        assert lst[0] == bulk_env["test_image"]

    def test_generate_upload_files(self, bulk_env):
        bulk_processor = bulk_env["bulk_processor"]
        mock_item_id = "mock_id"

        image_data, s3_manager, ovr_file = bulk_processor.generate_upload_files(bulk_env["test_image"], mock_item_id)

        assert image_data.width == 3376
        assert image_data.height == 2576

        assert isinstance(ovr_file, str)

        s3_url = S3Url(bulk_env["test_image"])
        assert s3_manager.s3_url.bucket == s3_url.bucket
        assert s3_manager.s3_url.key == s3_url.key
        assert s3_manager.s3_url.url == s3_url.url
        assert s3_manager.output_bucket == f"s3://{bulk_env['test_bucket']}"

        # clean up empty folder
        remove_folder = f"./test/data/{mock_item_id}"
        if os.path.exists(remove_folder):
            os.removedirs(remove_folder)

    def test_record_failed_image(self, bulk_env, tmp_path):
        bulk_processor = bulk_env["bulk_processor"]
        failed_manifest_file = str(tmp_path / "failed_images_manifest.json")
        bulk_processor.failed_manifest_path = failed_manifest_file

        bulk_processor.record_failed_image(bulk_env["error_details"])
        with open(failed_manifest_file, "r") as f:
            file_content = f.read()

        assert json.dumps(bulk_env["error_details"]) in file_content

    def test_bulk_add_image(self, bulk_env):
        bulk_processor = bulk_env["bulk_processor"]
        with patch("logging.Logger.info") as mock_info, patch(
            "stac_fastapi.opensearch.database_logic.DatabaseLogic.bulk_sync", new_callable=MagicMock
        ) as mock_bulk_item:
            mock_bulk_item.return_value.set_result(None)
            mock_collection_name = "test-collection"
            bulk_processor.submit_bulk_data_catalog(mock_collection_name, bulk_env["stac_items"])
            mock_info.assert_called_with(
                f"Successfully bulk inserted {len(bulk_env['stac_items'])} item(s) to the {mock_collection_name} collection!"
            )

    def test_failed_bulk_add_image(self, bulk_env):
        bulk_processor = bulk_env["bulk_processor"]
        with patch("logging.Logger.error") as mock_error, patch(
            "stac_fastapi.opensearch.database_logic.DatabaseLogic.bulk_sync", new_callable=MagicMock
        ) as mock_bulk_item:
            mock_bulk_item.side_effect = Exception("Unable to submit data catalog item...")
            with pytest.raises(Exception):
                bulk_processor.submit_bulk_data_catalog("test-collection", bulk_env["stac_items"])
            mock_error.assert_called_once()

    def test_record_failed_image_exception(self, bulk_env):
        bulk_processor = bulk_env["bulk_processor"]
        with patch("logging.Logger.error") as mock_error, patch("builtins.open", new_callable=mock_open) as mocked_open:
            mocked_open.side_effect = IOError("Failed to open file")

            bulk_processor.record_failed_image(bulk_env["error_details"])

            mock_error.assert_called_with(
                f"Failed to record failed image details in {bulk_processor.failed_manifest_path}: Failed to open file"
            )
