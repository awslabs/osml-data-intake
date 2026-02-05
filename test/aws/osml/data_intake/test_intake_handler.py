#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

import json
from unittest.mock import MagicMock, patch

import pytest

from aws.osml.data_intake.intake_handler import (
    GEOJSON_EXTENSIONS,
    IMAGE_EXTENSIONS,
    detect_file_type,
    handler,
)


class TestDetectFileType:
    """Test suite for the detect_file_type function."""

    def test_detect_tiff_files(self):
        """Test detection of TIFF image files."""
        assert detect_file_type("s3://bucket/image.tif") == "image"
        assert detect_file_type("s3://bucket/image.tiff") == "image"
        assert detect_file_type("s3://bucket/path/to/IMAGE.TIF") == "image"

    def test_detect_nitf_files(self):
        """Test detection of NITF image files."""
        assert detect_file_type("s3://bucket/image.ntf") == "image"
        assert detect_file_type("s3://bucket/image.nitf") == "image"

    def test_detect_jp2_files(self):
        """Test detection of JPEG2000 image files."""
        assert detect_file_type("s3://bucket/image.jp2") == "image"
        assert detect_file_type("s3://bucket/image.j2k") == "image"

    def test_detect_other_image_files(self):
        """Test detection of other image formats."""
        assert detect_file_type("s3://bucket/image.png") == "image"
        assert detect_file_type("s3://bucket/image.jpg") == "image"
        assert detect_file_type("s3://bucket/image.jpeg") == "image"
        assert detect_file_type("s3://bucket/image.img") == "image"

    def test_detect_geojson_files(self):
        """Test detection of GeoJSON files."""
        assert detect_file_type("s3://bucket/data.geojson") == "geojson"
        assert detect_file_type("s3://bucket/data.json") == "geojson"
        assert detect_file_type("s3://bucket/path/to/DATA.GEOJSON") == "geojson"

    def test_unsupported_file_type(self):
        """Test that unsupported file types raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            detect_file_type("s3://bucket/document.pdf")
        assert "Unsupported file type" in str(exc_info.value)
        assert ".pdf" in str(exc_info.value)

    def test_no_extension(self):
        """Test that files without extension raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            detect_file_type("s3://bucket/noextension")
        assert "Unsupported file type" in str(exc_info.value)

    def test_extension_sets_are_disjoint(self):
        """Verify that IMAGE_EXTENSIONS and GEOJSON_EXTENSIONS don't overlap."""
        overlap = IMAGE_EXTENSIONS & GEOJSON_EXTENSIONS
        assert len(overlap) == 0, f"Extensions overlap: {overlap}"


class TestIntakeHandler:
    """Test suite for the unified intake handler."""

    def test_handler_routes_to_image_processor(self):
        """Test that image files are routed to ImageProcessor."""
        event = {
            "Records": [
                {
                    "Sns": {
                        "Message": json.dumps(
                            {
                                "image_uri": "s3://bucket/image.tif",
                                "item_id": "test-item",
                                "collection_id": "test-collection",
                            }
                        )
                    }
                }
            ]
        }

        mock_processor = MagicMock()
        mock_processor.process.return_value = {"statusCode": 200, "body": "success"}

        with patch("aws.osml.data_intake.image_processor.ImageProcessor", return_value=mock_processor) as mock_class:
            result = handler(event, None)

        mock_class.assert_called_once()
        mock_processor.process.assert_called_once()
        assert result["statusCode"] == 200

    def test_handler_routes_to_geojson_processor(self):
        """Test that GeoJSON files are routed to GeoJSONProcessor."""
        event = {
            "Records": [
                {
                    "Sns": {
                        "Message": json.dumps(
                            {
                                "image_uri": "s3://bucket/data.geojson",
                                "item_id": "test-item",
                                "collection_id": "test-collection",
                            }
                        )
                    }
                }
            ]
        }

        mock_processor = MagicMock()
        mock_processor.process.return_value = {"statusCode": 200, "body": "success"}

        with patch("aws.osml.data_intake.geojson_processor.GeoJSONProcessor", return_value=mock_processor) as mock_class:
            result = handler(event, None)

        mock_class.assert_called_once()
        mock_processor.process.assert_called_once()
        assert result["statusCode"] == 200

    def test_handler_missing_image_uri(self):
        """Test that handler returns error when image_uri is missing."""
        event = {
            "Records": [
                {
                    "Sns": {
                        "Message": json.dumps(
                            {
                                "item_id": "test-item",
                                "collection_id": "test-collection",
                            }
                        )
                    }
                }
            ]
        }

        result = handler(event, None)

        assert result["statusCode"] == 400
        assert "image_uri" in result["body"]

    def test_handler_unsupported_file_type(self):
        """Test that handler returns error for unsupported file types."""
        event = {
            "Records": [
                {
                    "Sns": {
                        "Message": json.dumps(
                            {
                                "image_uri": "s3://bucket/document.pdf",
                                "item_id": "test-item",
                                "collection_id": "test-collection",
                            }
                        )
                    }
                }
            ]
        }

        result = handler(event, None)

        assert result["statusCode"] == 400
        assert "Unsupported file type" in result["body"]

    def test_handler_with_json_extension(self):
        """Test that .json files are routed to GeoJSONProcessor."""
        event = {
            "Records": [
                {
                    "Sns": {
                        "Message": json.dumps(
                            {
                                "image_uri": "s3://bucket/features.json",
                                "item_id": "test-item",
                                "collection_id": "test-collection",
                            }
                        )
                    }
                }
            ]
        }

        mock_processor = MagicMock()
        mock_processor.process.return_value = {"statusCode": 200, "body": "success"}

        with patch("aws.osml.data_intake.geojson_processor.GeoJSONProcessor", return_value=mock_processor):
            result = handler(event, None)

        assert result["statusCode"] == 200

    @pytest.mark.parametrize(
        "extension,expected_type",
        [
            (".tif", "image"),
            (".tiff", "image"),
            (".ntf", "image"),
            (".nitf", "image"),
            (".jp2", "image"),
            (".j2k", "image"),
            (".png", "image"),
            (".jpg", "image"),
            (".jpeg", "image"),
            (".img", "image"),
            (".geojson", "geojson"),
            (".json", "geojson"),
        ],
    )
    def test_all_supported_extensions(self, extension, expected_type):
        """Test all supported file extensions are correctly detected."""
        assert detect_file_type(f"s3://bucket/file{extension}") == expected_type
