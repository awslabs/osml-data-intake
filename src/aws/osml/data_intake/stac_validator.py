#  Copyright 2025 Amazon.com, Inc. or its affiliates.

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, Dict, Union

import jsonschema
from pystac import STACObjectType, STACValidationError
from pystac.validation import JsonSchemaSTACValidator
from pystac.validation.schema_uri_map import SchemaUriMap
from stac_fastapi.types.stac import Item

from .utils import logger


class StacValidationError(Exception):
    """Exception raised when STAC validation fails."""

    pass


class LocalReferenceResolver:
    """
    Local reference resolver for complete schema validation.

    Resolves external schema references using cached local files.
    Compatible with jsonschema<4.18 using RefResolver.
    """

    def __init__(self, schemas_dir: Path) -> None:
        """
        Initialize the local reference resolver.

        :param schemas_dir: Path to the schemas directory containing local schema cache
        """
        self.schemas_dir = schemas_dir
        self._store = {}
        self._build_store()

    def _build_store(self) -> None:
        """
        Build schema store for RefResolver.

        Loads all STAC and GeoJSON schemas from local cache into a store dict
        for use with jsonschema RefResolver.

        :returns: None
        """
        self._load_geojson_schemas()
        self._load_stac_schemas()

    def _load_geojson_schemas(self) -> None:
        """
        Load GeoJSON schemas into the store.

        :returns: None
        """
        geojson_geometry_types = [
            "Feature",
            "Geometry",
            "FeatureCollection",
            "Point",
            "LineString",
            "Polygon",
            "MultiPoint",
            "MultiLineString",
            "MultiPolygon",
        ]
        geojson_mappings = {
            f"https://geojson.org/schema/{name}.json": f"geojson/{name}.json" for name in geojson_geometry_types
        }
        missing_schemas = []
        for remote_uri, local_path in geojson_mappings.items():
            full_local_path = self.schemas_dir / local_path
            if full_local_path.exists():
                try:
                    with open(full_local_path) as f:
                        schema_data = json.load(f)

                    # Add schema to store for RefResolver
                    self._store[remote_uri] = schema_data
                    logger.debug(f"Schema loaded: {remote_uri} -> {local_path}")

                except Exception as err:
                    logger.error(f"Schema error: Could not load {local_path}: {err}")
                    missing_schemas.append(f"{remote_uri} -> {local_path} (error: {err})")
            else:
                logger.warning(f"Schema missing: {remote_uri} -> {local_path} (file not found)")
                missing_schemas.append(f"{remote_uri} -> {local_path} (missing)")

        if missing_schemas:
            logger.warning("Could not load geojson schemas:")
            for missing in missing_schemas:
                logger.warning(f"  {missing}")

    def _load_stac_schemas(self) -> None:
        """
        Load STAC schemas into the store.

        :returns: None
        """
        stac_dir = self.schemas_dir / "stac"
        if stac_dir.exists():
            for version_dir in stac_dir.glob("v*"):
                if version_dir.is_dir():
                    for schema_file in version_dir.rglob("*.json"):
                        try:
                            with open(schema_file) as f:
                                schema_data = json.load(f)

                            # Create remote URI from file path
                            relative_path = schema_file.relative_to(stac_dir)
                            remote_uri = f"https://schemas.stacspec.org/{relative_path}"

                            # Add schema to store
                            self._store[remote_uri] = schema_data

                        except Exception as err:
                            logger.warning(f"Could not load STAC schema {schema_file.relative_to(stac_dir)}: {err}")

    def get_store(self) -> Dict[str, Any]:
        """
        Get the schema store for RefResolver.

        :returns: Dictionary containing all loaded schemas
        """
        return self._store


class LocalSchemaUriMap(SchemaUriMap):
    """
    Custom schema URI map for local validation.

    Maps STAC object types to local schema file paths using organized
    directory structure: schemas/stac/ and schemas/geojson/
    """

    def __init__(self, schemas_dir: Path) -> None:
        """
        Initialize the local schema URI mapper.

        :param schemas_dir: Path to the schemas directory containing organized schema cache
        """
        self.schemas_dir = schemas_dir
        self.local_resolver = LocalReferenceResolver(schemas_dir)
        super().__init__()

    def get_object_schema_uri(self, object_type: STACObjectType, stac_version: str) -> str:
        """
        Get schema URI for a STAC object type and version.

        :param object_type: The type of STAC object (ITEM, COLLECTION, CATALOG)
        :param stac_version: The STAC version to validate against
        :returns: File URI pointing to local schema file
        :raises ValueError: If object_type is not supported
        :raises FileNotFoundError: If no compatible schema is found locally
        """

        # Generate paths for organized structure
        schema_paths = {
            STACObjectType.ITEM: f"stac/v{stac_version}/item-spec/json-schema/item.json",
            STACObjectType.COLLECTION: f"stac/v{stac_version}/collection-spec/json-schema/collection.json",
            STACObjectType.CATALOG: f"stac/v{stac_version}/catalog-spec/json-schema/catalog.json",
        }

        if object_type not in schema_paths:
            raise ValueError(f"Unsupported STAC object type: {object_type}")

        # Check if exact version exists
        schema_path = schema_paths[object_type]
        local_path = self.schemas_dir / schema_path

        if local_path.exists():
            return f"file://{local_path.absolute()}"

        # Find compatible version fallback
        stac_dir = self.schemas_dir / "stac"
        available_versions = []

        for version_dir in stac_dir.glob("v*"):
            if version_dir.is_dir():
                version_schema_path = schema_paths[object_type].replace(
                    f"stac/v{stac_version}/", f"stac/{version_dir.name}/"
                )
                candidate_path = self.schemas_dir / version_schema_path
                if candidate_path.exists():
                    version_num = version_dir.name[1:]
                    available_versions.append((version_num, version_dir.name, candidate_path))

        if available_versions:

            def version_key(version_tuple):
                parts = []
                for part in version_tuple[0].split("."):
                    try:
                        parts.append(int(part))
                    except ValueError:
                        parts.append(0)
                return parts

            available_versions.sort(key=version_key, reverse=True)
            _, fallback_version_name, fallback_path = available_versions[0]
            logger.warning(f"STAC v{stac_version} not found, using {fallback_version_name}")
            return f"file://{fallback_path.absolute()}"

        raise FileNotFoundError(
            f"No local STAC schema found for {object_type} v{stac_version}. "
            f"Run 'python scripts/update_stac_schemas.py' to download schemas."
        )


class LocalJsonSchemaValidator(JsonSchemaSTACValidator):
    """
    Local JSON Schema validator with complete reference resolution.

    Uses cached local schemas for validation without network dependencies.
    Handles external references through local schema registry.
    """

    def __init__(self, schema_uri_map: LocalSchemaUriMap) -> None:
        """
        Initialize the local JSON schema validator.

        :param schema_uri_map: URI mapper for locating local schema files
        """
        super().__init__(schema_uri_map)
        self.schema_uri_map = schema_uri_map

    def _validate_from_uri(self, stac_dict, stac_object_type, schema_uri, href=None) -> None:
        """
        Validate STAC object using local reference resolution.

        :param stac_dict: STAC object data to validate
        :param stac_object_type: Type of STAC object being validated
        :param schema_uri: URI of the schema to validate against
        :param href: Optional href of the STAC object being validated
        :returns: None
        :raises STACValidationError: If validation fails
        """
        try:
            # Load the main schema
            if schema_uri.startswith("file://"):
                schema_path = schema_uri.replace("file://", "")
                with open(schema_path) as f:
                    main_schema = json.load(f)

                # Log schema selection for debugging
                stac_id = stac_dict.get("id", "unknown")
                geom_type = stac_dict.get("geometry", {}).get("type", "unknown")
                logger.debug(f"STAC Validator - Item: {stac_id} - Geometry: {geom_type} - Schema: {schema_path}")
            else:
                return super()._validate_from_uri(stac_dict, stac_object_type, schema_uri, href)

            # Get schema store for jsonschema<4.18 RefResolver
            store = self.schema_uri_map.local_resolver.get_store()

            # Create RefResolver and validator for jsonschema<4.18
            resolver = jsonschema.RefResolver(base_uri="", referrer=main_schema, store=store)

            geometry = stac_dict.get("geometry", {})
            geom_type = geometry.get("type", "unknown")

            if geom_type == "MultiPolygon":  # For MultiPolygon geometries, bypass oneOf resolution issue
                self._validate_multipolygon(stac_dict, geometry, main_schema, store, resolver)
                return  # MultiPolygon validation completed successfully

            # Normal validation for non-MultiPolygon geometries
            validator = jsonschema.Draft7Validator(main_schema, resolver=resolver)
            errors = list(validator.iter_errors(stac_dict))

            if errors:
                stac_id = stac_dict.get("id", None)

                if "coordinates" in str(errors[0]) and geometry:
                    logger.error(f"Geometry validation failed - Item ID: {stac_id}")
                    logger.error(f"Geometry Type: {geom_type}")
                    logger.error(f"Schema Used: {schema_uri}")

                msg = f"Validation failed for {stac_object_type} "
                if href is not None:
                    msg += f"at {href} "
                if stac_id is not None:
                    msg += f"with ID {stac_id} "
                msg += f"against schema at {schema_uri}"

                best = jsonschema.exceptions.best_match(errors)
                if best:
                    msg += "\n" + str(best)
                raise STACValidationError(msg) from best

        except STACValidationError:
            raise
        except Exception as err:
            raise STACValidationError(f"Schema validation error: {err}")

    def _validate_multipolygon(self, stac_dict, geometry, stac_schema, store, resolver) -> None:
        """
        Handle MultiPolygon validation workaround for oneOf resolution issue.

        :param stac_dict: STAC object data to validate
        :param geometry: MultiPolygon geometry to validate
        :param stac_schema: STAC schema
        :param store: Schema store containing all loaded schemas
        :param resolver: JSON schema resolver
        :returns: None
        :raises STACValidationError: If MultiPolygon validation fails
        """
        stac_id = stac_dict.get("id", None)
        logger.debug(f"Multipolygon validation - Item ID: {stac_id}")

        # Use MultiPolygon schema directly instead of oneOf resolution
        multipolygon_schema_uri = "https://geojson.org/schema/MultiPolygon.json"
        if multipolygon_schema_uri in store:
            multipolygon_schema = store[multipolygon_schema_uri]

            # Create validator with MultiPolygon schema directly
            mp_validator = jsonschema.Draft7Validator(multipolygon_schema, resolver=resolver)
            mp_errors = list(mp_validator.iter_errors(geometry))

            if mp_errors:
                # MultiPolygon geometry validation failed
                best_mp_error = jsonschema.exceptions.best_match(mp_errors)
                raise STACValidationError(f"MultiPolygon geometry validation failed: {str(best_mp_error)}")
            else:
                logger.debug(f"MultiPolygon geometry validation PASSED for {stac_id}")

                # Now validate the STAC item with a simple Point geometry to bypass oneOf issues
                # Replace the MultiPolygon with a simple Point for STAC structure validation
                stac_dict_simple_geom = stac_dict.copy()
                stac_dict_simple_geom["geometry"] = {"type": "Point", "coordinates": [0, 0]}
                stac_dict_simple_geom["bbox"] = [0, 0, 0, 0]

                main_validator = jsonschema.Draft7Validator(stac_schema, resolver=resolver)
                main_errors = list(main_validator.iter_errors(stac_dict_simple_geom))

                if main_errors:
                    error = jsonschema.exceptions.best_match(main_errors)
                    raise STACValidationError(f"STAC item validation failed (structure): {str(error)}")

                logger.debug(f"STAC item validation PASSED for MultiPolygon item {stac_id}")
        else:
            msg = "MultiPolygon schema not found for validation"
            logger.error(msg)
            raise STACValidationError(msg)


def _get_schemas_directory() -> Path:
    """
    Get the schemas directory for STAC validation using package resources.

    Uses importlib.resources to access schemas bundled with the package.
    This works reliably across all deployment scenarios (local, Lambda, containers).

    :returns: Path to the schemas directory
    :raises FileNotFoundError: If schemas cannot be accessed
    """
    try:
        schemas_resource = files("aws.osml.data_intake") / "schemas"
        try:
            with schemas_resource as schema_path:
                return Path(schema_path)
        except TypeError:
            return Path(schemas_resource)
    except Exception as err:
        raise FileNotFoundError(f"Could not access schemas from package resources: {err}. ")


def validate_stac_item(item: Union[Dict[str, Any], Item, str]) -> None:
    """
    Validate a STAC Item using local schema resolution.

    :param item: STAC Item as Item, dictionary, or JSON string to validate.
                 Defaults to schema version 1.0.0 if not included in the item.
    :returns None
    :raises StacValidationError: If the item is not valid according to STAC specification
    """
    # Parse JSON string if needed
    if isinstance(item, str):
        try:
            item = json.loads(item)
        except json.JSONDecodeError as err:
            raise StacValidationError(f"Invalid JSON: {str(err)}")

    # Convert Item (TypedDict) to regular dict if it is not already
    if hasattr(item, "keys") and not isinstance(item, dict):
        item = dict(item)

    stac_version = item.get("stac_version", "1.0.0")

    try:
        # Use local reference resolution system
        schemas_dir = _get_schemas_directory()
        schema_uri_map = LocalSchemaUriMap(schemas_dir)
        validator = LocalJsonSchemaValidator(schema_uri_map)

        validator.validate_core(item, STACObjectType.ITEM, stac_version)

    except STACValidationError as err:
        raise StacValidationError(f"STAC validation failed: {str(err)}")
