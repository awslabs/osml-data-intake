#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

import json

from aws.osml.data_intake import processor_base


class DummyProcessor(processor_base.ProcessorBase):
    def process(self):
        return {"statusCode": 200, "body": json.dumps("ok")}


class DummyS3Manager:
    def __init__(self, output_bucket):
        self.output_bucket = output_bucket


class DummySNSManager:
    def __init__(self, output_topic):
        self.output_topic = output_topic


class DummySNSRequest:
    def __init__(self, **kwargs):
        self.data = kwargs


def test_success_message():
    message = "Processing completed successfully."
    expected_result = {"statusCode": 200, "body": json.dumps(message)}
    assert processor_base.ProcessorBase.success_message(message) == expected_result


def test_failure_message():
    exception_message = "An error occurred during processing."
    mock_exception = Exception(exception_message)

    result = processor_base.ProcessorBase.failure_message(mock_exception)
    result_body = json.loads(result["body"])

    assert result["statusCode"] == 500
    assert "message" in result_body
    assert "stack_trace" in result_body
    assert result_body["message"] == exception_message
    assert isinstance(result_body["stack_trace"], list)
    assert len(result_body["stack_trace"]) > 0


def test_processor_base_init_sets_dependencies(monkeypatch):
    monkeypatch.setattr(processor_base, "S3Manager", DummyS3Manager)
    monkeypatch.setattr(processor_base, "SNSManager", DummySNSManager)
    monkeypatch.setattr(processor_base, "SNSRequest", DummySNSRequest)

    message = json.dumps({"image_uri": "s3://bucket/key", "item_id": "item", "collection_id": "collection"})
    processor = DummyProcessor(message)

    assert isinstance(processor.s3_manager, DummyS3Manager)
    assert isinstance(processor.sns_manager, DummySNSManager)
    assert isinstance(processor.sns_request, DummySNSRequest)
