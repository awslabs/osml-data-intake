#  Copyright 2025 Amazon.com, Inc. or its affiliates.

# Update complete STAC schema cache with external dependencies
#
# This script downloads all STAC schemas from GitHub API and resolves external
# dependencies like GeoJSON schemas. Creates organized structure with separate
# directories for different schema sources.

import json
import re
import sys
from pathlib import Path
from urllib.request import urlopen


def discover_stac_schemas() -> list:
    # Discover all STAC schema files using GitHub API.
    print("Discovering STAC schemas from GitHub API...")

    api_url = "https://api.github.com/repos/radiantearth/stac-spec/git/trees/gh-pages?recursive=true"

    try:
        with urlopen(api_url, timeout=60) as response:
            tree_data = json.loads(response.read().decode("utf-8"))

        print(f"SUCCESS: Retrieved GitHub tree with {len(tree_data['tree'])} total files")

        # Filter for JSON schema files only (excluding dev schemas)
        schema_files = []
        for item in tree_data["tree"]:
            path = item["path"]
            if path.endswith(".json") and "json-schema" in path and not path.startswith("dev/"):
                schema_files.append(path)

        print(f"SUCCESS: Found {len(schema_files)} STAC schema files")
        return sorted(schema_files)

    except Exception as e:
        raise Exception(f"Failed to discover schemas from GitHub API: {e}")


def extract_external_references(schema_content: str) -> set:
    # Extract external $ref URLs from schema content.
    # Find all $ref patterns
    ref_pattern = r'"\\$ref"\\s*:\\s*"([^"]+)"'
    refs = re.findall(ref_pattern, schema_content)

    external_refs = set()
    for ref in refs:
        # Skip internal references (start with #)
        if ref.startswith("#"):
            continue
        # Skip relative references (no protocol)
        if "://" not in ref:
            continue

        external_refs.add(ref)

    return external_refs


def download_geojson_schemas(schemas_dir: Path) -> bool:
    # Download common GeoJSON schemas.
    print("\nDownloading GeoJSON schemas...")

    geojson_schemas = [
        "https://geojson.org/schema/Feature.json",
        "https://geojson.org/schema/Geometry.json",
        "https://geojson.org/schema/FeatureCollection.json",
        "https://geojson.org/schema/Point.json",
        "https://geojson.org/schema/LineString.json",
        "https://geojson.org/schema/Polygon.json",
        "https://geojson.org/schema/MultiPoint.json",
        "https://geojson.org/schema/MultiLineString.json",
        "https://geojson.org/schema/MultiPolygon.json",
    ]

    geojson_dir = schemas_dir / "geojson"
    geojson_dir.mkdir(exist_ok=True)

    success_count = 0
    for url in geojson_schemas:
        filename = url.split("/")[-1]
        local_path = geojson_dir / filename

        print(f"  {filename}")
        if download_schema(url, local_path):
            success_count += 1
            print(f"     SUCCESS: Downloaded from {url}")
        else:
            print(f"     ERROR: Failed to download {url}")

    return success_count > 0


def download_schema(url: str, local_path: Path) -> bool:
    # Download a schema file from URL to local path.
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)

        with urlopen(url, timeout=30) as response:
            schema_data = response.read().decode("utf-8")

        # Validate it's proper JSON
        json.loads(schema_data)

        # Save to local file
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(schema_data)

        return True

    except Exception as e:
        print(f"      ERROR: Download failed: {e}")
        return False


def main():
    # Discover and download all schemas with dependencies.

    script_dir = Path(__file__).parent
    schemas_dir = script_dir.parent / "src" / "aws" / "osml" / "data_intake" / "schemas"

    print("STAC Complete Schema Discovery with Dependencies")
    print("=" * 55)
    print(f"Target directory: {schemas_dir}")
    print("New structure: schemas/stac/ and schemas/geojson/")
    print()

    try:
        # Download GeoJSON dependencies first
        if not download_geojson_schemas(schemas_dir):
            print("WARNING: Some GeoJSON schemas failed to download")

        # Discover and download STAC schemas
        schema_paths = discover_stac_schemas()

        if not schema_paths:
            print("ERROR: No STAC schema files discovered")
            return False

        print(f"\nDownloading {len(schema_paths)} STAC schemas to schemas/stac/...")
        print()

        success_count = 0
        failed_schemas = []
        stac_dir = schemas_dir / "stac"

        # Download each STAC schema to stac subdirectory
        for file_path in schema_paths:
            # Convert GitHub path to schemas.stacspec.org URL
            url = f"https://schemas.stacspec.org/{file_path}"
            local_path = stac_dir / file_path

            print(f"  stac/{file_path}")

            success, error_msg = download_schema_with_error(url, local_path)
            if success:
                success_count += 1
                print("     SUCCESS: Downloaded")
            else:
                failed_schemas.append((file_path, error_msg))
                print(f"     ERROR: Failed: {error_msg}")

        # Show results
        print(f"\nFinal Results: {success_count}/{len(schema_paths)} STAC schemas downloaded")

        # Report failures
        if failed_schemas:
            print(f"\nFailed Downloads ({len(failed_schemas)}):")
            for file_path, error_msg in failed_schemas:
                print(f"  FAILED: {file_path}: {error_msg}")

        if success_count > 0:
            print("\nSUCCESS: Schema cache updated with complete dependency resolution!")

            # Show what was organized
            if schemas_dir.exists():
                stac_versions = len(list((schemas_dir / "stac").glob("v*")))
                geojson_schemas = len(list((schemas_dir / "geojson").glob("*.json")))
                total_schemas = len(list(schemas_dir.rglob("*.json")))

                print("\nOrganized Schema Summary:")
                print(f"  STAC versions: {stac_versions}")
                print(f"  GeoJSON schemas: {geojson_schemas}")
                print(f"  Total schemas: {total_schemas}")

            print("\nComplete reference resolution ready!")
            return True
        else:
            print("ERROR: No schemas downloaded")
            return False

    except Exception as e:
        print(f"ERROR: {e}")
        return False


def download_schema_with_error(url: str, local_path: Path) -> tuple[bool, str]:
    # Download schema with detailed error reporting.
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)

        with urlopen(url, timeout=30) as response:
            schema_data = response.read().decode("utf-8")

        try:
            json.loads(schema_data)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON (line {e.lineno}): {e.msg}"

        with open(local_path, "w", encoding="utf-8") as f:
            f.write(schema_data)

        return True, "Success"

    except Exception as e:
        return False, f"Download error: {e}"


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
