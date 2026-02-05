#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

import json

import boto3
import pytest
from moto import mock_aws

from aws.osml.data_intake.geojson_processor import (
    GeoJSONProcessor,
    extract_collection_from_key,
    generate_deterministic_id,
)
from aws.osml.data_intake.managers import S3Url
from aws.osml.data_intake.stac_validator import StacValidationError


class TestExtractCollectionFromKey:
    """Test suite for the extract_collection_from_key function."""

    def test_nested_path(self):
        """Test collection extraction from nested S3 path."""
        assert extract_collection_from_key("uploads/airports/airports-part-1.geojson") == "airports"

    def test_single_directory(self):
        """Test collection extraction with single directory."""
        assert extract_collection_from_key("cities/cities.geojson") == "cities"

    def test_root_file(self):
        """Test collection extraction from root file."""
        assert extract_collection_from_key("countries.geojson") == "countries"

    def test_underscore_replacement(self):
        """Test that underscores are replaced with hyphens."""
        assert extract_collection_from_key("data/my_collection/file.geojson") == "my-collection"

    def test_case_normalization(self):
        """Test that collection names are lowercased."""
        assert extract_collection_from_key("data/MyCollection/file.geojson") == "mycollection"

    def test_space_replacement(self):
        """Test that spaces are replaced with hyphens."""
        assert extract_collection_from_key("data/my collection/file.geojson") == "my-collection"

    def test_deeply_nested_path(self):
        """Test collection extraction from deeply nested path."""
        assert extract_collection_from_key("a/b/c/d/target/file.geojson") == "target"

    def test_json_extension(self):
        """Test collection extraction from .json file."""
        assert extract_collection_from_key("mydata.json") == "mydata"

    @pytest.mark.parametrize(
        "key,expected",
        [
            ("uploads/airports/file.geojson", "airports"),
            ("cities/data.json", "cities"),
            ("root-file.geojson", "root-file"),
            ("data/My_Collection/file.geojson", "my-collection"),
        ],
    )
    def test_various_paths(self, key, expected):
        """Test collection extraction with various path patterns."""
        assert extract_collection_from_key(key) == expected


class TestGenerateDeterministicId:
    """Test suite for the generate_deterministic_id function."""

    def test_deterministic_output(self):
        """Test that the same input produces the same ID."""
        feature = {
            "id": "feature-1",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {"name": "test"},
        }
        id1 = generate_deterministic_id(feature, "collection", "key")
        id2 = generate_deterministic_id(feature, "collection", "key")
        assert id1 == id2

    def test_different_features_different_ids(self):
        """Test that different features produce different IDs."""
        feature1 = {
            "id": "feature-1",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {},
        }
        feature2 = {
            "id": "feature-2",
            "geometry": {"type": "Point", "coordinates": [1, 1]},
            "properties": {},
        }
        id1 = generate_deterministic_id(feature1, "collection", "key")
        id2 = generate_deterministic_id(feature2, "collection", "key")
        assert id1 != id2

    def test_numeric_feature_id(self):
        """Test handling of numeric feature IDs."""
        feature = {
            "id": 12345,
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {},
        }
        result_id = generate_deterministic_id(feature, "collection", "key")
        assert "12345" in result_id

    def test_missing_feature_id(self):
        """Test handling of features without IDs."""
        feature = {
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {},
        }
        result_id = generate_deterministic_id(feature, "collection", "key")
        assert "feature" in result_id

    def test_different_collections_different_ids(self):
        """Test that same feature in different collections produces different IDs."""
        feature = {
            "id": "same-id",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {},
        }
        id1 = generate_deterministic_id(feature, "collection-a", "key")
        id2 = generate_deterministic_id(feature, "collection-b", "key")
        assert id1 != id2

    def test_id_format(self):
        """Test that generated ID has expected format."""
        feature = {
            "id": "my-feature",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {},
        }
        result_id = generate_deterministic_id(feature, "airports", "key")
        assert result_id.startswith("airports-my-feature-")
        # Should have a 12-character hash suffix
        parts = result_id.split("-")
        assert len(parts[-1]) == 12


@pytest.fixture
def mock_aws_env():
    """Set up mocked AWS environment with S3 and SNS."""
    with mock_aws():
        # Set up S3
        s3 = boto3.resource("s3", region_name="us-east-1")
        s3.meta.client.create_bucket(Bucket="test-bucket")

        # Create test GeoJSON data
        test_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "airport-1",
                    "geometry": {"type": "Point", "coordinates": [-122.4, 37.8]},
                    "properties": {"name": "SFO", "type": "international"},
                },
                {
                    "type": "Feature",
                    "id": "airport-2",
                    "geometry": {"type": "Point", "coordinates": [-118.4, 34.0]},
                    "properties": {"name": "LAX", "type": "international"},
                },
            ],
        }

        # Upload test GeoJSON to S3
        s3.meta.client.put_object(
            Bucket="test-bucket",
            Key="airports/test-airports.geojson",
            Body=json.dumps(test_geojson),
        )

        # Set up SNS
        sns = boto3.client("sns", region_name="us-east-1")
        response = sns.create_topic(Name="test-topic")
        sns_topic_arn = response["TopicArn"]

        yield {
            "s3": s3,
            "sns": sns,
            "sns_topic_arn": sns_topic_arn,
            "test_bucket": "test-bucket",
            "test_geojson": test_geojson,
        }


class TestGeoJSONProcessor:
    """Test suite for the GeoJSONProcessor class."""

    def test_process_success(self, mock_aws_env):
        """Test successful GeoJSON processing."""
        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/airports/test-airports.geojson",
            "item_id": "test-geojson-item",
            "collection_id": "OSML",
        }

        processor = GeoJSONProcessor(message=json.dumps(message))
        processor.sns_manager.sns_client = mock_aws_env["sns"]
        processor.sns_manager.output_topic = mock_aws_env["sns_topic_arn"]
        processor.s3_manager.s3_client = mock_aws_env["s3"]

        response = processor.process()

        assert response["statusCode"] == 200
        assert "successfully" in response["body"]
        assert "1/1" in response["body"]  # Default: single item for entire GeoJSON

    def test_process_success_deconstructs_feature_collection(self, mock_aws_env, monkeypatch):
        """Test deconstructing FeatureCollection when env var is enabled."""
        monkeypatch.setenv("DECONSTRUCT_FEATURE_COLLECTIONS", "true")
        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/airports/test-airports.geojson",
            "item_id": "test-geojson-item",
            "collection_id": "OSML",
        }

        processor = GeoJSONProcessor(message=json.dumps(message))
        processor.sns_manager.sns_client = mock_aws_env["sns"]
        processor.sns_manager.output_topic = mock_aws_env["sns_topic_arn"]
        processor.s3_manager.s3_client = mock_aws_env["s3"]

        response = processor.process()

        assert response["statusCode"] == 200
        assert "successfully" in response["body"]
        assert "2/2" in response["body"]  # 2 features published when deconstructing

    def test_process_single_feature(self, mock_aws_env):
        """Test processing a single Feature (not FeatureCollection)."""
        single_feature = {
            "type": "Feature",
            "id": "single-airport",
            "geometry": {"type": "Point", "coordinates": [-73.9, 40.7]},
            "properties": {"name": "JFK"},
        }

        mock_aws_env["s3"].meta.client.put_object(
            Bucket=mock_aws_env["test_bucket"],
            Key="airports/single.geojson",
            Body=json.dumps(single_feature),
        )

        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/airports/single.geojson",
            "item_id": "single-feature-item",
            "collection_id": "OSML",
        }

        processor = GeoJSONProcessor(message=json.dumps(message))
        processor.sns_manager.sns_client = mock_aws_env["sns"]
        processor.sns_manager.output_topic = mock_aws_env["sns_topic_arn"]
        processor.s3_manager.s3_client = mock_aws_env["s3"]

        response = processor.process()

        assert response["statusCode"] == 200
        assert "1/1" in response["body"]

    def test_process_invalid_geojson_type(self, mock_aws_env):
        """Test processing invalid GeoJSON type."""
        invalid_geojson = {"type": "Geometry", "coordinates": [0, 0]}

        mock_aws_env["s3"].meta.client.put_object(
            Bucket=mock_aws_env["test_bucket"],
            Key="invalid/invalid.geojson",
            Body=json.dumps(invalid_geojson),
        )

        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/invalid/invalid.geojson",
            "item_id": "invalid-item",
            "collection_id": "OSML",
        }

        processor = GeoJSONProcessor(message=json.dumps(message))
        processor.sns_manager.sns_client = mock_aws_env["sns"]
        processor.sns_manager.output_topic = mock_aws_env["sns_topic_arn"]
        processor.s3_manager.s3_client = mock_aws_env["s3"]

        response = processor.process()

        assert response["statusCode"] == 500
        assert "Invalid GeoJSON type" in response["body"]

    def test_collection_extraction_from_path(self, mock_aws_env):
        """Test that collection ID is extracted from S3 path when default is used."""
        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/airports/test-airports.geojson",
            "item_id": "test-geojson-item",
            "collection_id": "OSML",
        }

        processor = GeoJSONProcessor(message=json.dumps(message))
        processor.sns_manager.sns_client = mock_aws_env["sns"]
        processor.sns_manager.output_topic = mock_aws_env["sns_topic_arn"]
        processor.s3_manager.s3_client = mock_aws_env["s3"]

        response = processor.process()
        assert response["statusCode"] == 200

    def test_custom_collection_id(self, mock_aws_env):
        """Test that custom collection ID is used when provided."""
        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/airports/test-airports.geojson",
            "item_id": "test-item",
            "collection_id": "custom-collection",
        }

        processor = GeoJSONProcessor(message=json.dumps(message))
        processor.sns_manager.sns_client = mock_aws_env["sns"]
        processor.sns_manager.output_topic = mock_aws_env["sns_topic_arn"]
        processor.s3_manager.s3_client = mock_aws_env["s3"]

        response = processor.process()
        assert response["statusCode"] == 200

    def test_process_nonexistent_file(self, mock_aws_env):
        """Test processing a non-existent file."""
        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/nonexistent/file.geojson",
            "item_id": "nonexistent-item",
            "collection_id": "OSML",
        }

        processor = GeoJSONProcessor(message=json.dumps(message))
        processor.sns_manager.sns_client = mock_aws_env["sns"]
        processor.sns_manager.output_topic = mock_aws_env["sns_topic_arn"]
        processor.s3_manager.s3_client = mock_aws_env["s3"]

        response = processor.process()

        assert response["statusCode"] == 500

    def test_empty_feature_collection(self, mock_aws_env):
        """Test processing an empty FeatureCollection."""
        empty_geojson = {"type": "FeatureCollection", "features": []}

        mock_aws_env["s3"].meta.client.put_object(
            Bucket=mock_aws_env["test_bucket"],
            Key="empty/empty.geojson",
            Body=json.dumps(empty_geojson),
        )

        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/empty/empty.geojson",
            "item_id": "empty-item",
            "collection_id": "OSML",
        }

        processor = GeoJSONProcessor(message=json.dumps(message))
        processor.sns_manager.sns_client = mock_aws_env["sns"]
        processor.sns_manager.output_topic = mock_aws_env["sns_topic_arn"]
        processor.s3_manager.s3_client = mock_aws_env["s3"]

        response = processor.process()

        assert response["statusCode"] == 500
        assert "FeatureCollection contains no features" in response["body"]

    def test_feature_with_datetime_property(self, mock_aws_env):
        """Test processing features with datetime properties."""
        geojson_with_datetime = {
            "type": "Feature",
            "id": "dated-feature",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {"datetime": "2024-01-15T10:30:00Z", "name": "Test"},
        }

        mock_aws_env["s3"].meta.client.put_object(
            Bucket=mock_aws_env["test_bucket"],
            Key="dated/dated.geojson",
            Body=json.dumps(geojson_with_datetime),
        )

        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/dated/dated.geojson",
            "item_id": "dated-item",
            "collection_id": "OSML",
        }

        processor = GeoJSONProcessor(message=json.dumps(message))
        processor.sns_manager.sns_client = mock_aws_env["sns"]
        processor.sns_manager.output_topic = mock_aws_env["sns_topic_arn"]
        processor.s3_manager.s3_client = mock_aws_env["s3"]

        response = processor.process()

        assert response["statusCode"] == 200

    def test_build_stac_item(self, mock_aws_env):
        """Test building a STAC item produces expected fields."""
        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/airports/test-airports.geojson",
            "item_id": "test-geojson-item",
            "collection_id": "OSML",
        }

        processor = GeoJSONProcessor(message=json.dumps(message))
        s3_url = S3Url(message["image_uri"])
        item = processor._build_stac_item(
            item_id="item-1",
            geometry={"type": "Point", "coordinates": [0, 0]},
            bbox=[0, 0, 0, 0],
            properties={"datetime": "2024-01-15T10:30:00Z"},
            collection_id="collection-1",
            s3_url=s3_url,
        )

        assert item["id"] == "item-1"
        assert item["collection"] == "collection-1"
        assert item["assets"]["source"]["href"].startswith("s3://")
        assert len(item["links"]) == 2
        assert item["type"] == "Feature"
        assert item["stac_version"] == "1.0.0"

    def test_deconstructed_all_features_fail(self, mock_aws_env, monkeypatch):
        """Test that deconstructed mode returns 500 when all features fail validation."""
        monkeypatch.setenv("DECONSTRUCT_FEATURE_COLLECTIONS", "true")
        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/airports/test-airports.geojson",
            "item_id": "all-fail-test",
            "collection_id": "OSML",
        }

        processor = GeoJSONProcessor(message=json.dumps(message))
        processor.sns_manager.sns_client = mock_aws_env["sns"]
        processor.sns_manager.output_topic = mock_aws_env["sns_topic_arn"]
        processor.s3_manager.s3_client = mock_aws_env["s3"]

        monkeypatch.setattr(
            "aws.osml.data_intake.geojson_processor.validate_stac_item",
            lambda item: (_ for _ in ()).throw(StacValidationError("forced")),
        )

        response = processor.process()
        assert response["statusCode"] == 500
        assert "Failed to publish any STAC items" in response["body"]

    def test_deconstructed_partial_failure(self, mock_aws_env, monkeypatch):
        """Test partial failure: one feature fails validation, one succeeds."""
        monkeypatch.setenv("DECONSTRUCT_FEATURE_COLLECTIONS", "true")
        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/airports/test-airports.geojson",
            "item_id": "partial-test",
            "collection_id": "OSML",
        }

        processor = GeoJSONProcessor(message=json.dumps(message))
        processor.sns_manager.sns_client = mock_aws_env["sns"]
        processor.sns_manager.output_topic = mock_aws_env["sns_topic_arn"]
        processor.s3_manager.s3_client = mock_aws_env["s3"]

        call_count = 0

        def fail_first_only(item):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise StacValidationError("forced failure")

        monkeypatch.setattr(
            "aws.osml.data_intake.geojson_processor.validate_stac_item",
            fail_first_only,
        )

        response = processor.process()
        assert response["statusCode"] == 200
        assert "1/2" in response["body"]

    def test_download_returns_none_raises_clear_error(self, mock_aws_env, monkeypatch):
        """Test that a clear ValueError is raised when S3 download returns None."""
        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/airports/test-airports.geojson",
            "item_id": "none-download-test",
            "collection_id": "OSML",
        }
        processor = GeoJSONProcessor(message=json.dumps(message))
        processor.s3_manager.s3_client = mock_aws_env["s3"]

        monkeypatch.setattr(processor.s3_manager, "download_file", lambda s3_url: None)

        s3_url = S3Url(message["image_uri"])
        with pytest.raises(ValueError, match="Failed to download"):
            processor._download_and_parse_geojson(s3_url)

    def test_feature_with_null_geometry(self, mock_aws_env):
        """Test that a Feature with null geometry fails gracefully with validation error (not a crash)."""
        null_geom_feature = {
            "type": "Feature",
            "id": "null-geom",
            "geometry": None,
            "properties": {"name": "no-geometry"},
        }

        mock_aws_env["s3"].meta.client.put_object(
            Bucket=mock_aws_env["test_bucket"],
            Key="nullgeom/null.geojson",
            Body=json.dumps(null_geom_feature),
        )

        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/nullgeom/null.geojson",
            "item_id": "null-geom-item",
            "collection_id": "OSML",
        }

        processor = GeoJSONProcessor(message=json.dumps(message))
        processor.sns_manager.sns_client = mock_aws_env["sns"]
        processor.sns_manager.output_topic = mock_aws_env["sns_topic_arn"]
        processor.s3_manager.s3_client = mock_aws_env["s3"]

        # null geometry produces an empty dict which fails STAC validation
        # gracefully (returns 500), rather than crashing with AttributeError
        response = processor.process()
        assert response["statusCode"] == 500
        assert "validation" in response["body"].lower()

    def test_download_failure_preserves_exception_chain(self, mock_aws_env):
        """Test that download failures preserve the original exception chain."""
        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/nonexistent/file.geojson",
            "item_id": "chain-test",
            "collection_id": "OSML",
        }
        processor = GeoJSONProcessor(message=json.dumps(message))
        processor.s3_manager.s3_client = mock_aws_env["s3"]

        s3_url = S3Url(message["image_uri"])
        with pytest.raises(ValueError) as exc_info:
            processor._download_and_parse_geojson(s3_url)

        assert exc_info.value.__cause__ is not None

    def test_collection_bbox_ignores_null_geometry_features(self, mock_aws_env):
        """Test that null-geometry features don't inflate collection bbox to world bounds."""
        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/airports/test-airports.geojson",
            "item_id": "bbox-test",
            "collection_id": "OSML",
        }
        processor = GeoJSONProcessor(message=json.dumps(message))

        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": None, "properties": {}},
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [10, 20]}, "properties": {}},
            ],
        }

        bbox = processor._calculate_collection_bbox(geojson_data)
        assert bbox == [10, 20, 10, 20]

    def test_collection_bbox_all_null_geometries_returns_world_bounds(self, mock_aws_env):
        """Test that world bounds are returned when all features have null geometry."""
        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/airports/test-airports.geojson",
            "item_id": "bbox-all-null-test",
            "collection_id": "OSML",
        }
        processor = GeoJSONProcessor(message=json.dumps(message))

        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": None, "properties": {}},
                {"type": "Feature", "geometry": None, "properties": {}},
            ],
        }

        bbox = processor._calculate_collection_bbox(geojson_data)
        assert bbox == [-180, -90, 180, 90]

    def test_feature_count_always_present_in_feature_collection(self, mock_aws_env):
        """Test that feature_count is always set for FeatureCollections, even with empty properties."""
        geojson = {
            "type": "FeatureCollection",
            "properties": {},
            "features": [
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, 0]}, "properties": {}},
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [1, 1]}, "properties": {}},
            ],
        }
        mock_aws_env["s3"].meta.client.put_object(
            Bucket=mock_aws_env["test_bucket"],
            Key="fc/test.geojson",
            Body=json.dumps(geojson),
        )
        message = {
            "image_uri": f"s3://{mock_aws_env['test_bucket']}/fc/test.geojson",
            "item_id": "fc-props-test",
            "collection_id": "OSML",
        }
        processor = GeoJSONProcessor(message=json.dumps(message))
        processor.s3_manager.s3_client = mock_aws_env["s3"]

        s3_url = S3Url(message["image_uri"])
        stac_item = processor._create_stac_item_from_geojson(geojson, s3_url, "test-collection")

        assert stac_item["properties"]["feature_count"] == 2
