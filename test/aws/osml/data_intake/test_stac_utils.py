#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

import pytest

from aws.osml.data_intake.stac_utils import (
    WORLD_BOUNDS_BBOX,
    build_stac_item,
    build_stac_links,
    calculate_bbox_from_coords,
    calculate_bbox_from_geometry,
    geometry_from_bbox,
    get_current_datetime_iso,
    stac_item_to_dict,
)

# ---------------------------------------------------------------------------
# get_current_datetime_iso
# ---------------------------------------------------------------------------


def test_get_current_datetime_iso() -> None:
    result = get_current_datetime_iso()
    assert result.endswith("Z")
    assert "+" not in result


# ---------------------------------------------------------------------------
# build_stac_links
# ---------------------------------------------------------------------------


def test_build_stac_links() -> None:
    links = build_stac_links("my-collection", "item-123")
    assert len(links) == 2
    assert links[0]["rel"] == "self"
    assert links[0]["href"] == "/collections/my-collection/items/item-123"
    assert links[1]["rel"] == "collection"


# ---------------------------------------------------------------------------
# stac_item_to_dict
# ---------------------------------------------------------------------------


def test_stac_item_to_dict_with_dict() -> None:
    item = {"id": "test", "type": "Feature"}
    assert stac_item_to_dict(item) == item


def test_stac_item_to_dict_raises_for_non_mapping() -> None:
    with pytest.raises(TypeError, match="Expected a dict-like STAC Item"):
        stac_item_to_dict("not-a-dict")


# ---------------------------------------------------------------------------
# calculate_bbox_from_coords
# ---------------------------------------------------------------------------


def test_calculate_bbox_from_coords() -> None:
    coords = [[0.0, 0.0], [10.0, 5.0], [5.0, 10.0]]
    bbox = calculate_bbox_from_coords(coords)
    assert bbox == [0.0, 0.0, 10.0, 10.0]


# ---------------------------------------------------------------------------
# WORLD_BOUNDS_BBOX
# ---------------------------------------------------------------------------


def test_world_bounds_bbox_value() -> None:
    assert WORLD_BOUNDS_BBOX == [-180, -90, 180, 90]


# ---------------------------------------------------------------------------
# calculate_bbox_from_geometry
# ---------------------------------------------------------------------------


class TestCalculateBboxFromGeometry:
    """Test suite for the calculate_bbox_from_geometry function."""

    def test_point_geometry(self):
        geometry = {"type": "Point", "coordinates": [10.0, 20.0]}
        assert calculate_bbox_from_geometry(geometry) == [10.0, 20.0, 10.0, 20.0]

    def test_linestring_geometry(self):
        geometry = {"type": "LineString", "coordinates": [[0, 0], [10, 10], [20, 5]]}
        assert calculate_bbox_from_geometry(geometry) == [0, 0, 20, 10]

    def test_polygon_geometry(self):
        geometry = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
        }
        assert calculate_bbox_from_geometry(geometry) == [0, 0, 10, 10]

    def test_multipolygon_geometry(self):
        geometry = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[0, 0], [5, 0], [5, 5], [0, 5], [0, 0]]],
                [[[10, 10], [20, 10], [20, 20], [10, 20], [10, 10]]],
            ],
        }
        assert calculate_bbox_from_geometry(geometry) == [0, 0, 20, 20]

    def test_multipoint_geometry(self):
        geometry = {"type": "MultiPoint", "coordinates": [[0, 0], [5, 5], [10, 2]]}
        assert calculate_bbox_from_geometry(geometry) == [0, 0, 10, 5]

    def test_multilinestring_geometry(self):
        geometry = {
            "type": "MultiLineString",
            "coordinates": [
                [[0, 0], [5, 5]],
                [[10, 10], [15, 15]],
            ],
        }
        assert calculate_bbox_from_geometry(geometry) == [0, 0, 15, 15]

    def test_empty_geometry(self):
        geometry = {"type": "Unknown", "coordinates": []}
        assert calculate_bbox_from_geometry(geometry) == [-180, -90, 180, 90]

    def test_geometry_collection(self):
        geometry = {
            "type": "GeometryCollection",
            "geometries": [
                {"type": "Point", "coordinates": [5, 5]},
                {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]},
            ],
        }
        assert calculate_bbox_from_geometry(geometry) == [0, 0, 10, 10]

    def test_empty_geometry_collection(self):
        geometry = {"type": "GeometryCollection", "geometries": []}
        assert calculate_bbox_from_geometry(geometry) == [-180, -90, 180, 90]

    def test_nested_geometry_collection(self):
        geometry = {
            "type": "GeometryCollection",
            "geometries": [
                {
                    "type": "GeometryCollection",
                    "geometries": [
                        {"type": "Point", "coordinates": [5, 5]},
                        {"type": "Point", "coordinates": [15, 15]},
                    ],
                },
                {"type": "Point", "coordinates": [0, 0]},
            ],
        }
        assert calculate_bbox_from_geometry(geometry) == [0, 0, 15, 15]

    def test_missing_coordinates(self):
        geometry = {"type": "Point"}
        assert calculate_bbox_from_geometry(geometry) == [-180, -90, 180, 90]


# ---------------------------------------------------------------------------
# geometry_from_bbox
# ---------------------------------------------------------------------------


class TestGeometryFromBbox:
    """Test suite for the geometry_from_bbox function."""

    def test_returns_polygon(self):
        result = geometry_from_bbox([0.0, 0.0, 10.0, 10.0])
        assert result["type"] == "Polygon"

    def test_coordinates_form_closed_ring(self):
        result = geometry_from_bbox([0.0, 0.0, 10.0, 10.0])
        ring = result["coordinates"][0]
        assert len(ring) == 5
        assert ring[0] == ring[-1]

    def test_bbox_values_in_coordinates(self):
        result = geometry_from_bbox([-122.5, 37.5, -122.0, 38.0])
        ring = result["coordinates"][0]
        lons = [c[0] for c in ring]
        lats = [c[1] for c in ring]
        assert min(lons) == -122.5
        assert max(lons) == -122.0
        assert min(lats) == 37.5
        assert max(lats) == 38.0


# ---------------------------------------------------------------------------
# build_stac_item
# ---------------------------------------------------------------------------


class TestBuildStacItem:
    """Test suite for the build_stac_item function."""

    def _make_item(self, **overrides):
        defaults = {
            "item_id": "test-item",
            "collection_id": "test-collection",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "bbox": [0, 0, 0, 0],
            "properties": {"datetime": "2024-01-01T00:00:00Z"},
            "assets": {"data": {"href": "s3://bucket/key", "title": "Data", "type": "image/tiff", "roles": ["data"]}},
        }
        defaults.update(overrides)
        return build_stac_item(**defaults)

    def test_returns_dict_like_item(self):
        item = self._make_item()
        assert item["id"] == "test-item"
        assert item["collection"] == "test-collection"

    def test_has_required_stac_fields(self):
        item = self._make_item()
        assert item["type"] == "Feature"
        assert item["stac_version"] == "1.0.0"

    def test_auto_generates_links(self):
        item = self._make_item()
        links = item["links"]
        assert len(links) == 2
        assert links[0]["rel"] == "self"
        assert links[1]["rel"] == "collection"

    def test_custom_links_override(self):
        custom_links = [{"href": "/custom", "rel": "custom"}]
        item = self._make_item(links=custom_links)
        assert item["links"] == custom_links

    def test_geometry_and_bbox_passed_through(self):
        geom = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
        bbox = [0, 0, 1, 1]
        item = self._make_item(geometry=geom, bbox=bbox)
        assert item["geometry"] == geom
        assert item["bbox"] == bbox

    def test_properties_passed_through(self):
        props = {"datetime": "2024-06-15T12:00:00Z", "description": "test"}
        item = self._make_item(properties=props)
        assert item["properties"] == props
