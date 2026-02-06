# Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

from unittest.mock import patch

import boto3
import pytest
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError
from moto import mock_aws

from aws.osml.data_intake.managers.s3_manager import S3Manager, S3Url


class TestS3Url:
    """A test suite for the S3Url class in the AWS OSML data intake module."""

    def test_initialization(self):
        """
        Test the initialization of the S3Url class.

        Asserts that the bucket name, key, and full URL are correctly extracted from an S3 URL.
        """
        url = "s3://bucketname/example/object.txt"
        s3_url = S3Url(url)
        assert s3_url.bucket == "bucketname"
        assert s3_url.key == "example/object.txt"
        assert s3_url.url == url
        assert s3_url.prefix == "example"
        assert s3_url.filename == "object.txt"

    def test_key_with_query_string(self):
        url = "s3://my-bucket/path/to/object?param1=value1&param2=value2"
        s3_url = S3Url(url)
        expected_key = "path/to/object?param1=value1&param2=value2"
        assert s3_url.key == expected_key


@pytest.fixture
def s3_env():
    """Set up the test environment for S3Manager tests."""
    with mock_aws():
        s3_client = boto3.resource("s3", region_name="us-east-1")
        bucket_name = "output_bucket"
        s3_client.meta.client.create_bucket(Bucket=bucket_name)
        s3_manager = S3Manager(bucket_name)
        yield s3_client, s3_manager, bucket_name


class TestS3Manager:
    """A test suite for the S3Manager class in the AWS OSML data intake module."""

    def test_download_file(self, s3_env):
        """
        Test the download functionality of S3Manager.

        Ensures a file can be downloaded from S3 and is correctly placed in the local temporary directory.
        """
        s3_client, s3_manager, _ = s3_env
        s3_url = S3Url("s3://output_bucket/test_download_file.txt")
        s3_client.meta.client.put_object(Bucket=s3_url.bucket, Key=s3_url.key, Body=b"Hello world!")
        file_path = s3_manager.download_file(s3_url)

        with open(file_path, "rb") as f:
            content = f.read()
        assert content == b"Hello world!"

    def test_upload_file(self, s3_env, tmp_path):
        """
        Test the upload functionality of S3Manager.

        Ensures a file can be uploaded to S3 and verifies the uploaded content matches the local file.
        """
        s3_client, s3_manager, bucket_name = s3_env
        file_path = tmp_path / "test_upload_file.txt"
        file_path.write_text("Upload me!")

        s3_manager.upload_file(str(file_path), "text file")
        response = s3_client.meta.client.get_object(Bucket=bucket_name, Key="test_upload_file.txt")
        data = response["Body"].read()
        assert data.decode() == "Upload me!"

    def test_download_file_client_error(self, s3_env):
        """
        Test error handling in download_file for non-existent buckets.

        Verifies that None is returned when attempting to download from a non-existent bucket.
        """
        _, s3_manager, _ = s3_env
        s3_url = S3Url("s3://nonexistent_bucket/test_download_file.txt")
        s3_path = s3_manager.download_file(s3_url)
        assert s3_path is None

    def test_download_file_404_error(self, s3_env):
        _, s3_manager, _ = s3_env
        with patch("logging.Logger.error") as mock_error, patch(
            "boto3.s3.transfer.S3Transfer.download_file"
        ) as download_file:
            download_file.side_effect = ClientError({"Error": {"Code": "404"}}, "unexpected")

            s3_url = S3Url("s3://my-bucket/my-key")
            s3_manager.download_file(s3_url)

            mock_error.assert_called_with(
                "S3 error: An error occurred (404) when calling the unexpected operation: Unknown The "
                + f"{s3_url.bucket} bucket does not exist!"
            )

    def test_download_file_403_error(self, s3_env):
        _, s3_manager, _ = s3_env
        with patch("logging.Logger.error") as mock_error, patch(
            "boto3.s3.transfer.S3Transfer.download_file"
        ) as download_file:
            download_file.side_effect = ClientError({"Error": {"Code": "403"}}, "unexpected")

            s3_url = S3Url("s3://my-bucket/my-key")
            s3_manager.download_file(s3_url)

            mock_error.assert_called_with(
                "S3 error: An error occurred (403) when calling the unexpected operation: Unknown You"
                + " do not have permission to access "
                + f"{s3_url.bucket} bucket!"
            )

    def test_download_file_exception_error(self, s3_env):
        _, s3_manager, _ = s3_env
        with patch("boto3.s3.transfer.S3Transfer.download_file") as download_file:
            download_file.side_effect = Exception("Unexpected")

            s3_url = S3Url("s3://my-bucket/my-key")
            s3_manager.download_file(s3_url)

    def test_upload_file_client_error(self, s3_env, tmp_path):
        """
        Test error handling in upload_file for incorrect bucket permissions.

        Verifies that an S3UploadFailedError is raised when attempting to upload to a bucket with incorrect permissions.
        """
        _, s3_manager, _ = s3_env
        file_path = tmp_path / "test_upload_file.txt"
        file_path.write_text("Upload me!")
        s3_manager.output_bucket = "non-exist-bucket"
        with pytest.raises(S3UploadFailedError):
            s3_manager.upload_file(str(file_path), "text file")
