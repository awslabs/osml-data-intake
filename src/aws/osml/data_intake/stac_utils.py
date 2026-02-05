#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

"""
Shared STAC and GeoJSON geometry utilities.

Provides common functions for bounding box calculation, geometry conversion,
STAC link generation, and STAC item construction used by both the
ImageProcessor and GeoJSONProcessor.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from stac_fastapi.types.stac import Item

from .utils import logger

# Fallback bounding box covering the entire world
WORLD_BOUNDS_BBOX = [-180, -90, 180, 90]


def get_current_datetime_iso() -> str:
    """Return current UTC datetime in ISO format for STAC properties."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_stac_links(collection_id: str, item_id: str) -> List[Dict[str, str]]:
    """Build standard STAC self and collection links."""
    return [
        {"href": f"/collections/{collection_id}/items/{item_id}", "rel": "self"},
        {"href": f"/collections/{collection_id}", "rel": "collection", "type": "application/json"},
    ]


def stac_item_to_dict(stac_item: Item) -> Dict[str, Any]:
    """Convert STAC Item to dictionary for JSON serialization.

    :param stac_item: A STAC Item (TypedDict, dict, or mapping).
    :returns: The item as a plain dictionary.
    :raises TypeError: If the item is not a dict-like object.
    """
    if isinstance(stac_item, dict):
        return stac_item
    if hasattr(stac_item, "keys"):
        return dict(stac_item)
    raise TypeError(f"Expected a dict-like STAC Item, got {type(stac_item).__name__}")


def calculate_bbox_from_coords(coordinates: List[List[float]]) -> List[float]:
    """Calculate [min_lon, min_lat, max_lon, max_lat] from coordinate list."""
    lons = [coord[0] for coord in coordinates]
    lats = [coord[1] for coord in coordinates]
    return [min(lons), min(lats), max(lons), max(lats)]


def calculate_bbox_from_geometry(geometry: Dict[str, Any]) -> List[float]:
    """
    Calculate bounding box from a GeoJSON geometry object.

    Handles all standard GeoJSON geometry types: Point, LineString,
    MultiPoint, Polygon, MultiLineString, MultiPolygon, and
    GeometryCollection.

    :param geometry: GeoJSON geometry object with ``type`` and ``coordinates``.
    :returns: Bounding box as [min_lon, min_lat, max_lon, max_lat].
        Returns world bounds if the geometry is empty or unrecognised.
    """

    def _extract_coordinates(geom: Dict) -> List[List[float]]:
        """Extract all coordinate pairs from any geometry type."""
        geom_type = geom.get("type")
        coords = geom.get("coordinates", [])

        if geom_type == "Point":
            return [coords]
        elif geom_type in ["LineString", "MultiPoint"]:
            return coords
        elif geom_type in ["Polygon", "MultiLineString"]:
            return [coord for ring in coords for coord in ring]
        elif geom_type == "MultiPolygon":
            return [coord for polygon in coords for ring in polygon for coord in ring]
        elif geom_type == "GeometryCollection":
            all_coords = []
            for sub_geom in geom.get("geometries", []):
                all_coords.extend(_extract_coordinates(sub_geom))
            return all_coords
        else:
            return []

    try:
        coordinates = _extract_coordinates(geometry)
        if not coordinates:
            return list(WORLD_BOUNDS_BBOX)

        return calculate_bbox_from_coords(coordinates)
    except Exception as e:
        logger.warning(f"Could not calculate bbox from geometry: {e}")
        return list(WORLD_BOUNDS_BBOX)


def geometry_from_bbox(bbox: List[float]) -> Dict[str, Any]:
    """
    Create a GeoJSON Polygon geometry from a bounding box.

    :param bbox: Bounding box as [min_lon, min_lat, max_lon, max_lat].
    :returns: GeoJSON Polygon geometry dict.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


def build_stac_item(
    item_id: str,
    collection_id: str,
    geometry: Dict[str, Any],
    bbox: List[float],
    properties: Dict[str, Any],
    assets: Dict[str, Any],
    links: Optional[List[Dict[str, str]]] = None,
) -> Item:
    """
    Assemble a STAC Item from its components.

    Centralises the common dict structure (``type``, ``stac_version``) so that
    both ImageProcessor and GeoJSONProcessor share a single construction path.

    :param item_id: Unique identifier for the STAC item.
    :param collection_id: The STAC collection this item belongs to.
    :param geometry: GeoJSON geometry for the item.
    :param bbox: Bounding box as [min_lon, min_lat, max_lon, max_lat].
    :param properties: Properties dict (must include ``datetime``).
    :param assets: Assets dict keyed by asset role/name.
    :param links: Optional STAC links list.  When ``None``, standard self
        and collection links are generated via :func:`build_stac_links`.
    :returns: A STAC ``Item``.
    """
    if links is None:
        links = build_stac_links(collection_id, item_id)

    item_data = {
        "id": item_id,
        "collection": collection_id,
        "type": "Feature",
        "geometry": geometry,
        "bbox": bbox,
        "properties": properties,
        "assets": assets,
        "links": links,
        "stac_version": "1.0.0",
    }

    return Item(**item_data)
