#  Copyright 2025 Amazon.com, Inc. or its affiliates.

import json
from pathlib import Path

import pytest
from pystac import STACObjectType

from aws.osml.data_intake.stac_validator import (
    LocalJsonSchemaValidator,
    LocalReferenceResolver,
    LocalSchemaUriMap,
    StacValidationError,
    _get_schemas_directory,
    validate_stac_item,
)


class TestValidateStacItem:
    """Test cases for STAC item validator."""

    def get_valid_stac_item(self):
        """Return a valid STAC item for testing."""
        return {
            "stac_version": "1.0.0",
            "type": "Feature",
            "id": "test-item-1",
            "geometry": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
            "bbox": [-122.4194, 37.7749, -122.4194, 37.7749],
            "properties": {"datetime": "2023-01-01T12:00:00Z"},
            "links": [{"rel": "self", "href": "https://example.com/items/test-item-1"}],
            "assets": {"thumbnail": {"href": "https://example.com/thumb.jpg", "type": "image/jpeg", "roles": ["thumbnail"]}},
        }

    def test_valid_item_no_exception(self):
        """Test that a valid STAC item does not raise an exception."""
        item = self.get_valid_stac_item()
        try:
            validate_stac_item(item)
        except StacValidationError:
            pytest.fail("Valid STAC item should not raise StacValidationError")

    def test_invalid_item_raises_exception(self):
        """Test that an invalid STAC item raises StacValidationError."""
        invalid_item = {
            "stac_version": "1.0.0",
            "type": "InvalidType",  # Should be "Feature"
            "id": "invalid-item",
            # Missing required fields
        }

        with pytest.raises(StacValidationError):
            validate_stac_item(invalid_item)

    def test_missing_required_fields(self):
        """Test validation with missing required fields."""
        item = {"type": "Feature"}  # Missing most required fields

        with pytest.raises(StacValidationError) as exc_info:
            validate_stac_item(item)

        # Check that the error message is informative
        assert "STAC validation failed" in str(exc_info.value)

    def test_invalid_geometry_type(self):
        """Test validation with invalid geometry type."""
        item = self.get_valid_stac_item()
        item["geometry"]["type"] = "InvalidGeometryType"

        with pytest.raises(StacValidationError):
            validate_stac_item(item)

    def test_invalid_stac_version(self):
        """Test validation with invalid STAC version."""
        item = self.get_valid_stac_item()
        item["stac_version"] = "invalid-version"

        with pytest.raises(StacValidationError):
            validate_stac_item(item)

    def test_invalid_type_field(self):
        """Test validation with invalid type field."""
        item = self.get_valid_stac_item()
        item["type"] = "InvalidType"

        with pytest.raises(StacValidationError):
            validate_stac_item(item)

    def test_empty_id(self):
        """Test validation with empty id."""
        item = self.get_valid_stac_item()
        item["id"] = ""

        with pytest.raises(StacValidationError):
            validate_stac_item(item)

    def test_valid_complex_geometry(self):
        """Test validation with complex polygon geometry."""
        item = self.get_valid_stac_item()
        item["geometry"] = {
            "type": "Polygon",
            "coordinates": [
                [
                    [-122.4194, 37.7749],
                    [-122.4094, 37.7749],
                    [-122.4094, 37.7849],
                    [-122.4194, 37.7849],
                    [-122.4194, 37.7749],
                ]
            ],
        }
        item["bbox"] = [-122.4194, 37.7749, -122.4094, 37.7849]

        try:
            validate_stac_item(item)
            # Should not raise exception
        except StacValidationError:
            pytest.fail("Valid polygon item should be valid")

    def test_json_string_input(self):
        """Test validation with JSON string input."""
        item = self.get_valid_stac_item()
        item_json = json.dumps(item)

        try:
            validate_stac_item(item_json)
            # Should not raise exception
        except StacValidationError:
            pytest.fail("Valid STAC item as JSON string should be valid")

    def test_invalid_json_string(self):
        """Test validation with invalid JSON string."""
        invalid_json = '{"invalid": json}'

        with pytest.raises(StacValidationError) as exc_info:
            validate_stac_item(invalid_json)

        assert "Invalid JSON" in str(exc_info.value)


class TestMultiVersionSupport:
    """Test cases for multi-version STAC support."""

    def test_version_1_0_0(self):
        """Test validation with STAC version 1.0.0."""
        item = {
            "stac_version": "1.0.0",
            "type": "Feature",
            "id": "v1.0.0-test",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "bbox": [0, 0, 0, 0],
            "properties": {"datetime": "2023-01-01T12:00:00Z"},
            "links": [{"rel": "self", "href": "https://example.com/item"}],
            "assets": {"data": {"href": "https://example.com/data.tif"}},
        }

        try:
            validate_stac_item(item)
            # Should not raise exception
        except StacValidationError:
            pytest.fail("Valid STAC v1.0.0 item should validate")

    def test_version_1_1_0(self):
        """Test validation with STAC version 1.1.0."""
        item = {
            "stac_version": "1.1.0",
            "type": "Feature",
            "id": "v1.1.0-test",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "bbox": [0, 0, 0, 0],
            "properties": {"datetime": "2023-01-01T12:00:00Z"},
            "links": [{"rel": "self", "href": "https://example.com/item"}],
            "assets": {"data": {"href": "https://example.com/data.tif"}},
        }

        try:
            validate_stac_item(item)
            # Should not raise exception
        except StacValidationError:
            pytest.fail("Valid STAC v1.1.0 item should validate")

    def test_unsupported_version_fallback(self):
        """Test validation with unsupported version (should use fallback)."""
        item = {
            "stac_version": "999.0.0",  # Non-existent version
            "type": "Feature",
            "id": "fallback-test",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "bbox": [0, 0, 0, 0],
            "properties": {"datetime": "2023-01-01T12:00:00Z"},
            "links": [{"rel": "self", "href": "https://example.com/item"}],
            "assets": {"data": {"href": "https://example.com/data.tif"}},
        }

        # This should either work (with version fallback) or fail gracefully
        # Either outcome is acceptable as long as it doesn't crash
        try:
            validate_stac_item(item)
        except StacValidationError:
            pass  # Expected if version validation is strict


class TestCompleteReferenceResolution:
    """Test cases for complete external reference resolution system."""

    def test_geojson_reference_resolution(self):
        """Test that external GeoJSON references are resolved offline."""
        # This item will trigger GeoJSON schema references
        item = {
            "stac_version": "1.0.0",
            "type": "Feature",
            "id": "geojson-ref-test",
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
            "bbox": [0, 0, 1, 1],
            "properties": {"datetime": "2023-01-01T12:00:00Z"},
            "links": [{"rel": "self", "href": "https://example.com/item"}],
            "assets": {"data": {"href": "https://example.com/data.tif"}},
        }

        try:
            validate_stac_item(item)
            # Should work with complete reference resolution
        except StacValidationError:
            pytest.fail("Item with GeoJSON references should validate with complete resolution")

    def test_organized_schema_structure(self):
        """Test that validator works with organized schema directory structure."""
        # Verify we can get the schemas directory via package resources
        try:
            schemas_dir = _get_schemas_directory()
            assert schemas_dir.exists(), f"Schemas directory should exist at {schemas_dir}"

            # Verify organized structure exists
            assert (schemas_dir / "stac").exists(), f"schemas/stac/ directory should exist at {schemas_dir / 'stac'}"
            assert (
                schemas_dir / "geojson"
            ).exists(), f"schemas/geojson/ directory should exist at {schemas_dir / 'geojson'}"

            # Verify key schema files exist
            stac_versions = list((schemas_dir / "stac").glob("v*"))
            assert len(stac_versions) > 0, f"At least one STAC version should exist in {schemas_dir / 'stac'}"

            assert (
                schemas_dir / "geojson" / "Feature.json"
            ).exists(), f"Feature.json should exist at {schemas_dir / 'geojson' / 'Feature.json'}"
            assert (
                schemas_dir / "geojson" / "Geometry.json"
            ).exists(), f"Geometry.json should exist at {schemas_dir / 'geojson' / 'Geometry.json'}"
        except FileNotFoundError:
            pytest.skip("Schemas not available - run 'python scripts/update_stac_schemas.py' to download schemas")

    def test_complex_item_with_extensions(self):
        """Test validation of item that would trigger complex reference resolution."""
        item = {
            "stac_version": "1.0.0",
            "type": "Feature",
            "id": "complex-item",
            "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]]},
            "bbox": [0, 0, 1, 1],
            "properties": {"datetime": "2023-01-01T12:00:00Z", "title": "Test item with complex geometry"},
            "links": [
                {"rel": "self", "href": "https://example.com/item"},
                {"rel": "collection", "href": "https://example.com/collection"},
            ],
            "assets": {
                "data": {"href": "https://example.com/data.tif", "type": "image/tiff", "roles": ["data"]},
                "thumbnail": {"href": "https://example.com/thumb.jpg", "type": "image/jpeg", "roles": ["thumbnail"]},
            },
            "collection": "test-collection",
        }

        try:
            validate_stac_item(item)
            # Complex item should validate with complete reference resolution
        except StacValidationError:
            pytest.fail("Complex item should validate with complete reference resolution")


class TestLocalReferenceResolver:
    """Test cases for LocalReferenceResolver."""

    def test_missing_schemas_directory(self):
        """Test handling of missing schemas directory."""
        # Use a non-existent directory
        non_existent_dir = Path("/non/existent/schemas/dir")
        resolver = LocalReferenceResolver(non_existent_dir)

        # Should not crash, but store should be empty or minimal
        store = resolver.get_store()
        assert isinstance(store, dict)

    def test_corrupted_schema_file(self, tmp_path):
        """Test handling of corrupted schema files."""
        # Create temp directory with corrupted schema
        geojson_dir = tmp_path / "geojson"
        geojson_dir.mkdir()

        # Create corrupted JSON file
        corrupted_schema = geojson_dir / "Feature.json"
        corrupted_schema.write_text("{ invalid json }")

        resolver = LocalReferenceResolver(tmp_path)
        store = resolver.get_store()

        # Should handle error gracefully
        assert isinstance(store, dict)


class TestLocalSchemaUriMap:
    """Test cases for LocalSchemaUriMap."""

    def test_unsupported_object_type(self):
        """Test error handling for unsupported STAC object type."""
        schema_map = LocalSchemaUriMap(Path("/tmp"))

        # Use an invalid object type (this should raise ValueError)
        with pytest.raises(ValueError, match="Unsupported STAC object type"):
            # Pass an invalid enum-like value
            class FakeObjectType:
                pass

            schema_map.get_object_schema_uri(FakeObjectType(), "1.0.0")

    def test_no_schema_found(self):
        """Test error when no schema files are found."""
        # Use empty directory
        empty_dir = Path("/tmp/empty")
        schema_map = LocalSchemaUriMap(empty_dir)

        with pytest.raises(FileNotFoundError, match="No local STAC schema found"):
            schema_map.get_object_schema_uri(STACObjectType.ITEM, "999.0.0")


class TestLocalJsonSchemaValidator:
    """Test cases for LocalJsonSchemaValidator."""

    def test_non_file_schema_uri(self):
        """Test handling of non-file schema URIs."""
        schema_map = LocalSchemaUriMap(Path("/tmp"))
        validator = LocalJsonSchemaValidator(schema_map)

        # Mock the parent class validation for non-file URIs
        test_item = {"type": "Feature", "id": "test"}

        # This should call super()._validate_from_uri for non-file URIs
        try:
            validator._validate_from_uri(test_item, STACObjectType.ITEM, "https://remote.schema.com/item.json")
        except Exception:
            pass  # Expected since we don't have real remote schema access


class TestMultiPolygonWorkaround:
    """Test cases specifically for MultiPolygon validation workaround."""

    def get_valid_multipolygon_item(self):
        """Return a valid STAC item with MultiPolygon geometry."""
        return {
            "stac_version": "1.0.0",
            "type": "Feature",
            "id": "multipolygon-test",
            "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]]},
            "bbox": [0, 0, 1, 1],
            "properties": {"datetime": "2023-01-01T12:00:00Z"},
            "links": [{"rel": "self", "href": "https://example.com/items/multipolygon-test"}],
            "assets": {"data": {"href": "https://example.com/data.tif"}},
        }

    def test_multipolygon_validation_success(self):
        """Test successful MultiPolygon validation."""
        item = self.get_valid_multipolygon_item()

        try:
            validate_stac_item(item)
        except StacValidationError:
            pytest.fail("Valid MultiPolygon item should validate successfully")

    def test_multipolygon_invalid_coordinates(self):
        """Test MultiPolygon with invalid coordinates."""
        item = self.get_valid_multipolygon_item()

        # Invalid MultiPolygon coordinates (wrong nesting level)
        item["geometry"]["coordinates"] = [[[0, 0], [1, 0], [1, 1]]]  # Missing proper nesting

        with pytest.raises(StacValidationError, match="MultiPolygon geometry validation failed"):
            validate_stac_item(item)


class TestErrorConditions:
    """Test cases for various error conditions and edge cases."""

    def test_schema_validation_generic_error(self):
        """Test handling of generic schema validation errors."""
        # Test with completely malformed data that would cause generic errors
        invalid_item = {
            "stac_version": "1.0.0",
            "type": "Feature",
            "id": None,  # Invalid ID type
            "geometry": {"type": "Point", "coordinates": "invalid"},  # Invalid coordinates
            "properties": {},  # Missing required datetime
        }

        with pytest.raises(StacValidationError):
            validate_stac_item(invalid_item)

    def test_schema_directory_access_failure(self, monkeypatch):
        """Test handling of schema directory access failures."""

        # Mock files() to raise exception
        def mock_files(package):
            raise Exception("Package resources not available")

        monkeypatch.setattr("aws.osml.data_intake.stac_validator.files", mock_files)

        with pytest.raises(FileNotFoundError, match="Could not access schemas from package resources"):
            _get_schemas_directory()

    def test_item_with_typed_dict_interface(self):
        """Test validation with TypedDict-like item."""

        # Create a mock object that has keys() but isn't a dict and is subscriptable
        class MockItem:
            def __init__(self):
                self.data = {
                    "stac_version": "1.0.0",
                    "type": "Feature",
                    "id": "mock-item",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "bbox": [0, 0, 0, 0],
                    "properties": {"datetime": "2023-01-01T12:00:00Z"},
                    "links": [{"rel": "self", "href": "https://example.com/item"}],
                    "assets": {"data": {"href": "https://example.com/data.tif"}},
                }

            def keys(self):
                return self.data.keys()

            def get(self, key, default=None):
                return self.data.get(key, default)

            def __getitem__(self, key):
                return self.data[key]

            def __iter__(self):
                return iter(self.data)

        mock_item = MockItem()

        # Should convert to dict and validate
        try:
            validate_stac_item(mock_item)
        except StacValidationError:
            pytest.fail("Mock TypedDict-like item should validate after conversion")

    def test_coordinate_validation_error_logging(self):
        """Test that coordinate validation errors are logged properly."""
        item = {
            "stac_version": "1.0.0",
            "type": "Feature",
            "id": "coord-error-test",
            "geometry": {"type": "Point", "coordinates": "not-an-array"},  # Invalid: coordinates must be array
            "bbox": [0, 0, 0, 0],
            "properties": {"datetime": "2023-01-01T12:00:00Z"},
            "links": [{"rel": "self", "href": "https://example.com/item"}],
            "assets": {"data": {"href": "https://example.com/data.tif"}},
        }

        with pytest.raises(StacValidationError):
            validate_stac_item(item)


class TestGeometryTypes:
    """Test cases for different geometry types."""

    def get_base_item(self):
        """Return base STAC item structure."""
        return {
            "stac_version": "1.0.0",
            "type": "Feature",
            "id": "geometry-test",
            "properties": {"datetime": "2023-01-01T12:00:00Z"},
            "links": [{"rel": "self", "href": "https://example.com/item"}],
            "assets": {"data": {"href": "https://example.com/data.tif"}},
        }

    def test_linestring_geometry(self):
        """Test validation with LineString geometry."""
        item = self.get_base_item()
        item["geometry"] = {"type": "LineString", "coordinates": [[0, 0], [1, 1], [2, 2]]}
        item["bbox"] = [0, 0, 2, 2]

        try:
            validate_stac_item(item)
        except StacValidationError:
            pytest.fail("Valid LineString item should validate")

    def test_multipoint_geometry(self):
        """Test validation with MultiPoint geometry."""
        item = self.get_base_item()
        item["geometry"] = {"type": "MultiPoint", "coordinates": [[0, 0], [1, 1], [2, 2]]}
        item["bbox"] = [0, 0, 2, 2]

        try:
            validate_stac_item(item)
        except StacValidationError:
            pytest.fail("Valid MultiPoint item should validate")

    def test_multilinestring_geometry(self):
        """Test validation with MultiLineString geometry."""
        item = self.get_base_item()
        item["geometry"] = {"type": "MultiLineString", "coordinates": [[[0, 0], [1, 1]], [[2, 2], [3, 3]]]}
        item["bbox"] = [0, 0, 3, 3]

        try:
            validate_stac_item(item)
        except StacValidationError:
            pytest.fail("Valid MultiLineString item should validate")


if __name__ == "__main__":
    pytest.main([__file__])
