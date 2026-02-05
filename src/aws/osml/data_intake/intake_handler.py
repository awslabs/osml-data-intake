#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

"""
Unified Intake Handler for OSML Data Intake Pipeline.

This module provides a single Lambda entry point that routes incoming SNS messages
to the appropriate processor based on file type (image or GeoJSON).
"""

import json
from pathlib import Path
from typing import Any, Dict

from .utils import logger

# Supported file extensions for each processor type
IMAGE_EXTENSIONS = {".tif", ".tiff", ".ntf", ".nitf", ".jp2", ".j2k", ".png", ".jpg", ".jpeg", ".img"}
GEOJSON_EXTENSIONS = {".geojson", ".json"}


def detect_file_type(uri: str) -> str:
    """
    Detect the file type from the URI based on file extension.

    :param uri: The S3 URI or file path to analyze.
    :returns: 'image' for image files, 'geojson' for GeoJSON files.
    :raises ValueError: If the file extension is not supported.
    """
    ext = Path(uri).suffix.lower()

    if ext in IMAGE_EXTENSIONS:
        return "image"
    elif ext in GEOJSON_EXTENSIONS:
        return "geojson"
    else:
        raise ValueError(f"Unsupported file type: '{ext}'. Supported extensions: {IMAGE_EXTENSIONS | GEOJSON_EXTENSIONS}")


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Unified AWS Lambda handler function that routes to the appropriate processor.

    This handler parses the incoming SNS message, detects the file type from the
    image_uri field, and delegates processing to either ImageProcessor or GeoJSONProcessor.

    :param event: The event payload containing the SNS message.
    :param context: The Lambda execution context (unused).
    :returns: The response from the appropriate processor.
    """
    # Extract the SNS message from the event
    message = event["Records"][0]["Sns"]["Message"]
    message_data = json.loads(message)

    # Get the file URI from the message
    file_uri = message_data.get("image_uri", "")

    if not file_uri:
        logger.error("No image_uri found in SNS message")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing required field: image_uri"}),
        }

    # Detect file type and route to appropriate processor
    try:
        file_type = detect_file_type(file_uri)
        logger.info(f"Detected file type '{file_type}' for URI: {file_uri}")
    except ValueError as e:
        logger.error(f"File type detection failed: {e}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": str(e)}),
        }

    # Route to the appropriate processor
    if file_type == "image":
        # Import here to avoid circular imports and GDAL initialization for non-image files
        from .image_processor import ImageProcessor

        logger.info("Routing to ImageProcessor")
        return ImageProcessor(message).process()

    elif file_type == "geojson":
        from .geojson_processor import GeoJSONProcessor

        logger.info("Routing to GeoJSONProcessor")
        return GeoJSONProcessor(message).process()

    # Unreachable: detect_file_type raises ValueError for unknown types
    raise RuntimeError(f"Unexpected file type: {file_type}")
