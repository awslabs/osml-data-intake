#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

from typing import Any, Dict

from aws.osml.data_intake.utils import logger

from .geojson_test import run_geojson_test
from .image_test import run_image_test
from .integ_utils import create_error_response, get_config


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Integration test Lambda handler.

    Routes to the appropriate test flow based on the event's 'test_type'.
    """
    try:
        config, error_response = get_config()
        if error_response:
            return error_response

        test_type = (event or {}).get("test_type", "image")
        if test_type == "geojson":
            return run_geojson_test(config, deconstruct=False)
        if test_type == "geojson_decomposed":
            return run_geojson_test(config, deconstruct=True)
        return run_image_test(config)

    except Exception as e:
        logger.error(f"Integration test failed: {e}", exc_info=True)
        return create_error_response(str(e))
