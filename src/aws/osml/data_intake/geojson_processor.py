#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

"""
GeoJSON Processor for OSML Data Intake Pipeline.

Processes pre-simplified GeoJSON files and converts them to STAC Items,
following the same pattern as ImageProcessor for consistency.
"""

import hashlib
import json
import os
from typing import Any, Dict, List, Optional

from stac_fastapi.types.stac import Item

from .managers import S3Url
from .processor_base import ProcessorBase
from .stac_utils import (
    WORLD_BOUNDS_BBOX,
    build_stac_item,
    calculate_bbox_from_geometry,
    geometry_from_bbox,
    get_current_datetime_iso,
    stac_item_to_dict,
)
from .stac_validator import StacValidationError, validate_stac_item
from .utils import AsyncContextFilter, logger

# Default collection ID assigned by CDK when no specific collection is requested
DEFAULT_COLLECTION_ID = "OSML"


def extract_collection_from_key(s3_key: str) -> str:
    """
    Extract collection name from S3 key directory path.

    Examples:
        - "uploads/airports/airports-part-1.geojson" -> "airports"
        - "data/cities/administrative-cities.geojson" -> "cities"
        - "countries.geojson" -> "countries"

    :param s3_key: The S3 object key.
    :returns: Collection name derived from the path.
    """
    path_parts = s3_key.split("/")

    if len(path_parts) < 2:
        # File is in root bucket, extract collection from filename
        filename = path_parts[0]
        if filename.lower().endswith(".geojson"):
            collection_base = filename.removesuffix(".geojson")
        else:
            collection_base = filename.rsplit(".", 1)[0]  # Remove any extension
    else:
        # Use the directory name (second to last component)
        collection_base = path_parts[-2]

    # Clean collection name for STAC compliance
    collection_name = collection_base.lower().replace("_", "-").replace(" ", "-")

    # Ensure we have a valid collection name
    if not collection_name:
        collection_name = "user-data"

    return collection_name


def generate_deterministic_id(feature: Dict[str, Any], collection_id: str, source_key: str) -> str:
    """
    Generate a deterministic ID based on feature content to prevent duplicates.

    :param feature: The GeoJSON feature.
    :param collection_id: The STAC collection ID.
    :param source_key: The S3 object key of the source file.
    :returns: A deterministic unique identifier for the feature.
    """
    hash_components = {
        "collection": collection_id,
        "source": source_key,
        "geometry": feature.get("geometry", {}),
        "properties": feature.get("properties", {}),
    }

    # Use feature ID if available (most stable identifier)
    if feature.get("id"):
        hash_components["feature_id"] = feature["id"]

    # Create deterministic hash
    hash_input = json.dumps(hash_components, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:12]

    # Create readable ID with hash suffix for uniqueness
    base_id = feature.get("id", "feature")
    if isinstance(base_id, (int, float)):
        base_id = str(base_id)
    elif not isinstance(base_id, str):
        base_id = "feature"

    # Clean base ID for STAC compliance
    base_id = str(base_id).replace(" ", "-").replace("_", "-").lower()

    return f"{collection_id}-{base_id}-{content_hash}"


class GeoJSONProcessor(ProcessorBase):
    """
    Processes GeoJSON files and converts them to STAC items.

    By default, the entire GeoJSON file is represented as a single STAC item.
    When deconstruction is enabled (via Lambda environment variable or S3 object
    tag ``DECONSTRUCT_FEATURE_COLLECTIONS``), each feature in a FeatureCollection
    is published as its own STAC item.

    :param message: The incoming SNS request message (JSON string).
    """

    def __init__(self, message: str) -> None:
        """
        Initialize a GeoJSONProcessor instance.

        :param message: The incoming SNS request message.
        :returns: None
        """
        super().__init__(message)
        self.deconstruct_feature_collections = (
            os.getenv("DECONSTRUCT_FEATURE_COLLECTIONS", "false").strip().lower() == "true"
        )

    def _get_deconstruct_setting_from_s3_tag(self, s3_url: S3Url) -> Optional[bool]:
        """Read DECONSTRUCT_FEATURE_COLLECTIONS tag from the S3 object."""
        try:
            tags = self.s3_manager.get_object_tagging(s3_url.bucket, s3_url.key)
            for tag in tags:
                if tag.get("Key") == "DECONSTRUCT_FEATURE_COLLECTIONS":
                    return tag.get("Value", "").strip().lower() == "true"
        except Exception as e:
            logger.warning(f"Could not read S3 tags for {s3_url.url}: {e}")
        return None

    def process(self) -> Dict[str, Any]:
        """
        Process the incoming SNS message, download the GeoJSON, and publish STAC items.

        :returns: A response indicating the status of the process.
        """
        try:
            AsyncContextFilter.set_context({"item_id": self.sns_request.item_id})
            logger.info(f"Processing GeoJSON file: {self.sns_request.image_uri}")

            s3_url = S3Url(self.sns_request.image_uri)

            tag_value = self._get_deconstruct_setting_from_s3_tag(s3_url)
            if tag_value is not None:
                self.deconstruct_feature_collections = tag_value
                logger.info(f"Using S3 tag DECONSTRUCT_FEATURE_COLLECTIONS={tag_value}")

            geojson_data = self._download_and_parse_geojson(s3_url)

            collection_id = self.sns_request.collection_id
            if collection_id == DEFAULT_COLLECTION_ID:
                collection_id = extract_collection_from_key(s3_url.key)
            logger.info(f"Using collection: {collection_id}")

            if self.deconstruct_feature_collections and geojson_data.get("type") == "FeatureCollection":
                return self._process_deconstructed(geojson_data.get("features", []), s3_url, collection_id)

            return self._process_single(geojson_data, s3_url, collection_id)

        except Exception as err:
            return self.failure_message(err)

    def _process_deconstructed(self, features: List[Dict[str, Any]], s3_url: S3Url, collection_id: str) -> Dict[str, Any]:
        """
        Process a FeatureCollection by creating a separate STAC item for each feature.

        :param features: List of GeoJSON features.
        :param s3_url: The S3 URL of the source file.
        :param collection_id: The STAC collection ID.
        :returns: A response indicating the status of the process.
        """
        logger.info(f"Processing {len(features)} GeoJSON features")
        published_count = 0

        for i, feature in enumerate(features):
            try:
                stac_item = self._create_stac_item(feature, s3_url, collection_id)

                try:
                    validate_stac_item(stac_item)
                except StacValidationError as validation_err:
                    logger.error(f"STAC item validation failed for feature {i}: {validation_err}")
                    continue

                stac_item_dict = stac_item_to_dict(stac_item)
                self.sns_manager.publish_message(json.dumps(stac_item_dict), subject=f"STAC Item: {stac_item_dict['id']}")
                published_count += 1
                logger.info(f"Published STAC item {i + 1}/{len(features)}: {stac_item_dict['id']}")

            except Exception as feature_error:
                logger.error(f"Failed to process feature {i}: {feature_error}")
                continue

        if published_count == 0:
            return self.failure_message(ValueError(f"Failed to publish any STAC items from {len(features)} features"))

        message = f"GeoJSON processed successfully: {published_count}/{len(features)} STAC items published"
        if published_count < len(features):
            logger.warning(f"Partial success: {len(features) - published_count} features failed")

        return self.success_message(message)

    def _process_single(self, geojson_data: Dict[str, Any], s3_url: S3Url, collection_id: str) -> Dict[str, Any]:
        """
        Create a single STAC item for the entire GeoJSON file (default mode).

        :param geojson_data: Parsed GeoJSON data.
        :param s3_url: The S3 URL of the source file.
        :param collection_id: The STAC collection ID.
        :returns: A response indicating the status of the process.
        """
        stac_item = self._create_stac_item_from_geojson(geojson_data, s3_url, collection_id)

        try:
            validate_stac_item(stac_item)
        except StacValidationError as validation_err:
            logger.error(f"STAC item validation failed: {validation_err}")
            return self.failure_message(validation_err)

        stac_item_dict = stac_item_to_dict(stac_item)
        self.sns_manager.publish_message(json.dumps(stac_item_dict), subject=f"STAC Item: {stac_item_dict['id']}")

        return self.success_message("GeoJSON processed successfully: 1/1 STAC items published")

    def _download_and_parse_geojson(self, s3_url: S3Url) -> Dict[str, Any]:
        """
        Download and parse a GeoJSON file from S3.

        :param s3_url: The parsed S3 URL object.
        :returns: Parsed GeoJSON data as a dictionary.
        :raises ValueError: If the file cannot be downloaded or parsed.
        """
        try:
            file_path = self.s3_manager.download_file(s3_url)
            if file_path is None:
                raise ValueError(f"Failed to download GeoJSON file from {s3_url.url}")

            with open(file_path, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)

            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Could not remove temp file {file_path}: {e}")

            return geojson_data

        except Exception as e:
            raise ValueError(f"Failed to download or parse GeoJSON file: {e}") from e

    def _create_stac_item(self, feature: Dict[str, Any], s3_url: S3Url, collection_id: str) -> Item:
        """
        Create a STAC Item from a single GeoJSON feature.

        :param feature: The GeoJSON feature.
        :param s3_url: The S3 URL of the source file.
        :param collection_id: The STAC collection ID.
        :returns: A STAC Item.
        """
        item_id = generate_deterministic_id(feature, collection_id, s3_url.key)

        geometry = feature.get("geometry") or {}
        bbox = calculate_bbox_from_geometry(geometry)
        properties = feature.get("properties", {}) or {}

        return self._build_stac_item(
            item_id=item_id,
            geometry=geometry,
            bbox=bbox,
            properties=properties,
            collection_id=collection_id,
            s3_url=s3_url,
        )

    def _calculate_collection_bbox(self, geojson_data: Dict[str, Any]) -> List[float]:
        """Calculate a bounding box for an entire GeoJSON file."""
        geojson_type = geojson_data.get("type")
        if geojson_type == "Feature":
            geometry = geojson_data.get("geometry") or {}
            return calculate_bbox_from_geometry(geometry)

        if geojson_type == "FeatureCollection":
            features = geojson_data.get("features", [])
            if not features:
                return list(WORLD_BOUNDS_BBOX)

            bboxes = [calculate_bbox_from_geometry(f.get("geometry") or {}) for f in features]
            # Filter out world-bounds fallbacks from features with null/invalid geometry
            valid_bboxes = [b for b in bboxes if b != list(WORLD_BOUNDS_BBOX)]
            if not valid_bboxes:
                return list(WORLD_BOUNDS_BBOX)

            return [
                min(b[0] for b in valid_bboxes),
                min(b[1] for b in valid_bboxes),
                max(b[2] for b in valid_bboxes),
                max(b[3] for b in valid_bboxes),
            ]

        return list(WORLD_BOUNDS_BBOX)

    def _create_stac_item_from_geojson(self, geojson_data: Dict[str, Any], s3_url: S3Url, collection_id: str) -> Item:
        """
        Create a single STAC Item representing the entire GeoJSON file.

        This is the default processing mode when deconstruction is disabled.
        For FeatureCollections the geometry is derived from the overall bounding
        box of all contained features.

        :param geojson_data: Parsed GeoJSON data (Feature or FeatureCollection).
        :param s3_url: The S3 URL of the source file.
        :param collection_id: The STAC collection ID.
        :returns: A STAC Item.
        """
        item_id = self.sns_request.item_id
        geometry: Dict[str, Any] = {}

        geojson_type = geojson_data.get("type")
        if geojson_type == "Feature":
            geometry = geojson_data.get("geometry") or {}
            properties = geojson_data.get("properties", {}) or {}
        elif geojson_type == "FeatureCollection":
            features = geojson_data.get("features", []) or []
            if not features:
                raise ValueError("FeatureCollection contains no features.")
            properties = geojson_data.get("properties") or {}
            properties.setdefault("feature_count", len(features))
        else:
            raise ValueError(f"Invalid GeoJSON type: {geojson_type}. Expected 'Feature' or 'FeatureCollection'.")

        bbox = self._calculate_collection_bbox(geojson_data)
        if geojson_type == "FeatureCollection":
            geometry = geometry_from_bbox(bbox)

        return self._build_stac_item(
            item_id=item_id,
            geometry=geometry,
            bbox=bbox,
            properties=properties,
            collection_id=collection_id,
            s3_url=s3_url,
        )

    def _build_stac_item(
        self,
        item_id: str,
        geometry: Dict[str, Any],
        bbox: List[float],
        properties: Dict[str, Any],
        collection_id: str,
        s3_url: S3Url,
    ) -> Item:
        """
        Build a STAC item from the given components.

        Prepares GeoJSON-specific properties and assets, then delegates to
        the shared :func:`~stac_utils.build_stac_item` constructor.

        :param item_id: Unique identifier for the STAC item.
        :param geometry: GeoJSON geometry for the item.
        :param bbox: Bounding box as [min_lon, min_lat, max_lon, max_lat].
        :param properties: Properties to include in the STAC item.
        :param collection_id: The STAC collection this item belongs to.
        :param s3_url: The S3 URL of the source GeoJSON file.
        :returns: A STAC ``Item``.
        """
        feature_datetime = properties.get("datetime") or properties.get("date")
        if not feature_datetime:
            feature_datetime = get_current_datetime_iso()

        stac_properties = {
            "datetime": feature_datetime,
            "data_type": "vector",
            "geometry_simplified": True,
            **{k: v for k, v in properties.items() if k not in ["datetime", "date"]},
        }

        assets = {
            "source": {
                "href": f"s3://{s3_url.bucket}/{s3_url.key}",
                "title": "Source GeoJSON",
                "type": "application/geo+json",
                "roles": ["data"],
            }
        }

        return build_stac_item(
            item_id=item_id,
            collection_id=collection_id,
            geometry=geometry,
            bbox=bbox,
            properties=stac_properties,
            assets=assets,
        )
