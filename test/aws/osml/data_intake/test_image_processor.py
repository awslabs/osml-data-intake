#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

import json
import os
import shutil

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def mock_image_env():
    with mock_aws():
        test_bucket = "test-bucket"
        test_topic = "test-topic"

        s3 = boto3.resource("s3", region_name="us-east-1")
        s3.meta.client.create_bucket(Bucket=test_bucket)
        s3.meta.client.upload_file("./test/data/small.tif", test_bucket, "small.tif")

        sns = boto3.client("sns", region_name="us-east-1")
        response = sns.create_topic(Name=test_topic)
        sns_topic_arn = response["TopicArn"]

        yield {
            "s3": s3,
            "sns": sns,
            "sns_topic_arn": sns_topic_arn,
            "test_bucket": test_bucket,
        }


@pytest.fixture
def image_processor(mock_image_env):
    from aws.osml.data_intake.image_processor import ImageProcessor

    message = {"image_uri": f"s3://{mock_image_env['test_bucket']}/small.tif", "item_id": "test_id"}
    processor = ImageProcessor(message=json.dumps(message))
    processor.sns_manager.sns_client = mock_image_env["sns"]
    processor.sns_manager.output_topic = mock_image_env["sns_topic_arn"]
    processor.s3_manager.s3_client = mock_image_env["s3"]
    processor.s3_manager.output_bucket = mock_image_env["test_bucket"]
    return processor


def test_process_success(image_processor):
    response = image_processor.process()

    assert response["statusCode"] == 200
    assert "successfully" in response["body"]


def test_process_failure(image_processor):
    image_processor.sns_request.image_uri = "s3://invalid-bucket/invalid-image.tif"
    response = image_processor.process()

    assert response["statusCode"] == 500
    assert "Unable to Load" in response["body"]


@pytest.fixture
def image_data(tmp_path):
    from aws.osml.data_intake.image_processor import ImageData

    original_source = "./test/data/small.tif"
    source_file = tmp_path / "small-test.tif"
    shutil.copyfile(original_source, source_file)
    image_data_instance = ImageData(str(source_file))

    yield image_data_instance, str(source_file)

    files_to_remove = [
        str(source_file),
        f"{source_file}.aux.xml",
        f"{source_file}.ovr",
        f"{source_file}.gdalinfo.json",
    ]
    image_data_instance.delete_files(files_to_remove)


def test_generate_metadata(image_data):
    image_data_instance, _ = image_data
    image_data_instance.generate_metadata()

    assert image_data_instance.dataset is not None
    assert image_data_instance.sensor_model is not None
    assert image_data_instance.width == image_data_instance.dataset.RasterXSize
    assert image_data_instance.height == image_data_instance.dataset.RasterYSize
    assert image_data_instance.image_corners == [
        [0, 0],
        [image_data_instance.width, 0],
        [image_data_instance.width, image_data_instance.height],
        [0, image_data_instance.height],
    ]


def test_create_image_data(image_data):
    image_data_instance, _ = image_data
    assert image_data_instance.geo_polygon is not None
    assert image_data_instance.geo_bbox is not None


def test_generate_aux_file(image_data):
    image_data_instance, source_file = image_data
    aux_file = image_data_instance.generate_aux_file()
    assert aux_file == f"{source_file}.aux.xml"
    assert os.path.exists(aux_file)


def test_generate_ovr_file(image_data):
    image_data_instance, source_file = image_data
    ovr_file = image_data_instance.generate_ovr_file()
    assert ovr_file == f"{source_file}.ovr"
    assert os.path.exists(ovr_file)


def test_generate_gdalinfo(image_data):
    image_data_instance, source_file = image_data
    info_file = image_data_instance.generate_gdalinfo()
    assert info_file == f"{source_file}.gdalinfo.json"
    assert os.path.exists(info_file)


def test_clean_dataset(image_data):
    image_data_instance, _ = image_data
    image_data_instance.clean_dataset()
    assert image_data_instance.dataset is None
