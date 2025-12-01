# Copyright 2024-2025 Amazon.com, Inc. or its affiliates.

import json
import os
import unittest
from unittest.mock import MagicMock, mock_open, patch

import boto3
import pytest
from moto import mock_aws


@mock_aws
class TestBulkProcessor(unittest.TestCase):
    def setUp(self):
        from aws.osml.data_intake.bulk_processor import BulkProcessor

        self.test_bucket = "test-bucket"
        self.failed_manifest_file = "./test/data/failed_images_manifest.json"
        self.test_image = f"s3://{self.test_bucket}/small.tif"
        self.aws_s3 = boto3.resource("s3", region_name="us-east-1")
        self.aws_s3.meta.client.create_bucket(Bucket=self.test_bucket)
        self.aws_s3.meta.client.upload_file("./test/data/small.tif", self.test_bucket, "small.tif")
        self.aws_s3.meta.client.upload_file("./test/data/manifest.json", self.test_bucket, "manifest.json")

        self.s3_uri = os.environ["S3_URI"]
        self.input_path = os.environ["S3_INPUT_PATH"]
        self.output_path = os.environ["S3_OUTPUT_PATH"]
        self.output_bucket = os.environ["S3_OUTPUT_BUCKET"]
        self.stac_endpoint = os.environ["STAC_ENDPOINT"]
        self.collection_id = os.environ["COLLECTION_ID"]
        self.bulk_processor = BulkProcessor(
            self.aws_s3, self.output_path, self.output_bucket, self.stac_endpoint, self.collection_id, self.input_path
        )

        self.error_details = {"image": self.test_image, "error": "TEST_ERROR", "internal_traceback": "TEST_TRACEBACK"}
        self.stac_items = [
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

    def test_process_manifest_file(self):
        from aws.osml.data_intake.bulk_processor import process_manifest_file

        lst = process_manifest_file(self.aws_s3, self.input_path, self.s3_uri)

        assert len(lst) == 1
        assert lst[0] == self.test_image

    def test_generate_upload_files(self):
        from aws.osml.data_intake.managers import S3Url

        mock_item_id = "mock_id"

        image_data, s3_manager, ovr_file = self.bulk_processor.generate_upload_files(self.test_image, mock_item_id)

        self.assertEqual(image_data.width, 3376)
        self.assertEqual(image_data.height, 2576)

        self.assertIsInstance(ovr_file, str)

        s3_url = S3Url(self.test_image)
        self.assertEqual(s3_manager.s3_url.bucket, s3_url.bucket)
        self.assertEqual(s3_manager.s3_url.key, s3_url.key)
        self.assertEqual(s3_manager.s3_url.url, s3_url.url)
        self.assertEqual(s3_manager.output_bucket, f"s3://{self.test_bucket}")

        # clean up empty folder
        remove_folder = f"./test/data/{mock_item_id}"
        if os.path.exists(remove_folder):
            os.removedirs(remove_folder)

    def test_record_failed_image(self):
        self.bulk_processor.record_failed_image(self.error_details)
        with open(self.failed_manifest_file, "r") as f:
            file_content = f.read()

        self.assertIn(json.dumps(self.error_details), file_content)
        if os.path.exists(self.failed_manifest_file):
            os.remove(self.failed_manifest_file)

    @patch("logging.Logger.info")
    @patch("stac_fastapi.opensearch.database_logic.DatabaseLogic.bulk_sync", new_callable=MagicMock)
    def test_bulk_add_image(self, mock_bulk_item, mock_info):
        mock_bulk_item.return_value.set_result(None)
        mock_collection_name = "test-collection"
        self.bulk_processor.submit_bulk_data_catalog(mock_collection_name, self.stac_items)  # stimulate bulk add
        mock_info.assert_called_with(
            f"Successfully bulk inserted {len(self.stac_items)} item(s) to the {mock_collection_name} collection!"
        )

    @patch("logging.Logger.error")
    @patch("stac_fastapi.opensearch.database_logic.DatabaseLogic.bulk_sync", new_callable=MagicMock)
    def test_failed_bulk_add_image(self, mock_bulk_item, mock_info):
        mock_bulk_item.side_effect = Exception("Unable to submit data catalog item...")
        with pytest.raises(Exception):
            self.bulk_processor.submit_bulk_data_catalog("test-collection", self.stac_items)  # stimulate bulk add
            mock_info.assert_called_with("Unable to submit data catalog item...")

    @patch("builtins.open", new_callable=mock_open)
    @patch("logging.Logger.error")
    def test_record_failed_image_exception(self, mock_error, mock_open):
        # Simulate an exception when opening the file
        mock_open.side_effect = IOError("Failed to open file")

        self.bulk_processor.record_failed_image(self.error_details)

        # Check that logging.error was called
        mock_error.assert_called_with(
            f"Failed to record failed image details in {self.failed_manifest_file}: Failed to open file"
        )


if __name__ == "__main__":
    unittest.main()
