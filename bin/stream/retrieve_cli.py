#  Copyright 2024-2025 Amazon.com, Inc. or its affiliates.

import argparse
import base64
import json
import sys
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3


class RetrieveCLI:
    def __init__(
        self,
        stac_endpoint: str,
        item_id: Optional[str] = None,
        collection_id: Optional[str] = None,
        limit: int = 100,
        bbox: Optional[str] = None,
        datetime: Optional[str] = None,
        token: Optional[str] = None,
    ) -> None:
        """
        Initializes the RetrieveCLI with STAC endpoint and query parameters.

        :param stac_endpoint: The base URL of the STAC API endpoint.
        :param item_id: The specific item ID to retrieve (optional).
        :param collection_id: The collection ID to search within (optional).
        :param limit: Maximum number of items to return (default: 100).
        :param bbox: Bounding box filter in format "minx,miny,maxx,maxy" (optional).
        :param datetime: Datetime filter in format "start/end" (optional).
        :param token: Authorization token for the API (optional).
        :returns: None
        """
        self.stac_endpoint = stac_endpoint.rstrip("/")
        self.item_id = item_id
        self.collection_id = collection_id
        self.limit = limit
        self.bbox = bbox
        self.datetime = datetime
        self.token = token

        # Set up headers
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def _make_request(self, method: str, url: str, data: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        Make an HTTP request using urllib.

        :param method: HTTP method (GET, POST, etc.)
        :param url: The URL to request
        :param data: Optional data to send with POST requests
        :returns: Response JSON as dictionary, or None if error
        """
        try:
            # Prepare request data
            request_data = None
            if data:
                request_data = json.dumps(data).encode("utf-8")

            # Create request
            req = Request(url, data=request_data, headers=self.headers, method=method.upper())

            # Make request
            with urlopen(req) as response:
                response_body = response.read().decode()
                if response.status == 404:
                    return None
                elif response.status >= 400:
                    print(f"HTTP error {response.status}: {response_body}")
                    # Try to parse as JSON for better error display
                    try:
                        error_json = json.loads(response_body)
                        if isinstance(error_json, dict) and "detail" in error_json:
                            print(f"Error detail: {error_json['detail']}")
                    except (json.JSONDecodeError, TypeError):
                        pass
                    return None

                # Handle base64-encoded responses (API Gateway may return base64)
                try:
                    # Try to decode as base64 first
                    decoded = base64.b64decode(response_body).decode("utf-8")
                    return json.loads(decoded)
                except (base64.binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
                    # If base64 decode fails, try parsing as plain JSON
                    return json.loads(response_body)

        except HTTPError as e:
            error_body = e.read().decode() if hasattr(e, "read") else str(e)
            if e.code == 404:
                return None
            else:
                print(f"HTTP error {e.code}: {error_body}")
                # Try to parse as JSON for better error display
                try:
                    error_json = json.loads(error_body)
                    if isinstance(error_json, dict) and "detail" in error_json:
                        print(f"Error detail: {error_json['detail']}")
                except (json.JSONDecodeError, TypeError):
                    pass
                return None
        except URLError as e:
            print(f"URL error: {e}")
            return None
        except Exception as e:
            print(f"Error making request: {e}")
            import traceback

            traceback.print_exc()
            return None

    def get_item(self, item_id: str, collection_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific STAC item by ID and collection.

        :param item_id: The ID of the item to retrieve.
        :param collection_id: The collection ID containing the item.
        :returns: The STAC item as a dictionary, or None if not found.
        """
        url = f"{self.stac_endpoint}/collections/{collection_id}/items/{item_id}"

        result = self._make_request("GET", url)
        if result is None:
            print(f"Item '{item_id}' not found in collection '{collection_id}'")
        return result

    def search_items(self) -> Dict[str, Any]:
        """
        Search for STAC items using the provided filters.

        :returns: A dictionary containing the search results.
        """
        url = f"{self.stac_endpoint}/search"

        # Build query parameters
        params = {"limit": self.limit}

        if self.collection_id:
            params["collections"] = [self.collection_id]

        if self.bbox:
            bbox_coords = [float(x.strip()) for x in self.bbox.split(",")]
            if len(bbox_coords) != 4:
                raise ValueError("Bbox must be in format 'minx,miny,maxx,maxy'")
            params["bbox"] = bbox_coords

        if self.datetime:
            params["datetime"] = self.datetime

        result = self._make_request("POST", url, params)
        if result is None:
            print("Error searching items")
            return {"features": [], "type": "FeatureCollection"}
        return result

    def list_collections(self) -> Dict[str, Any]:
        """
        List all available collections.

        :returns: A dictionary containing the collections.
        """
        url = f"{self.stac_endpoint}/collections"

        result = self._make_request("GET", url)
        if result is None:
            print("Error listing collections")
            return {"collections": []}
        return result

    def get_collection(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific collection by ID.

        :param collection_id: The ID of the collection to retrieve.
        :returns: The collection as a dictionary, or None if not found.
        """
        url = f"{self.stac_endpoint}/collections/{collection_id}"

        result = self._make_request("GET", url)
        if result is None:
            print(f"Collection '{collection_id}' not found")
        return result

    @staticmethod
    def _discover_stac_endpoint(region: str, export_name: str = "DataCatalog-StacApiUrl") -> Optional[str]:
        """
        Discover the STAC endpoint from CloudFormation exports.

        :param region: The AWS region to search in.
        :param export_name: The CloudFormation export name to look for (default: "DataCatalog-StacApiUrl").
        :returns: The STAC endpoint URL, or None if not found.
        """
        try:
            cf_client = boto3.client("cloudformation", region_name=region)

            # List all exports
            response = cf_client.list_exports()

            for export in response.get("Exports", []):
                if export["Name"] == export_name:
                    return export["Value"]

            # If not found in first page, paginate through all exports
            next_token = response.get("NextToken")
            while next_token:
                response = cf_client.list_exports(NextToken=next_token)
                for export in response.get("Exports", []):
                    if export["Name"] == export_name:
                        return export["Value"]
                next_token = response.get("NextToken")

            return None
        except Exception as e:
            print(f"Error discovering STAC endpoint: {e}")
            return None

    def run(self) -> None:
        """
        Execute the main retrieval process based on provided parameters.
        :returns: None
        """
        try:
            if self.item_id and self.collection_id:
                # Retrieve specific item
                print(f"Retrieving item '{self.item_id}' from collection '{self.collection_id}'...")
                item = self.get_item(self.item_id, self.collection_id)
                if item:
                    print(json.dumps(item, indent=2))
                else:
                    sys.exit(1)
            elif self.collection_id and not self.item_id:
                # Search items in specific collection
                print(f"Searching items in collection '{self.collection_id}'...")
                results = self.search_items()
                print(json.dumps(results, indent=2))
            else:
                # List all collections
                print("Listing all collections...")
                collections = self.list_collections()
                print(json.dumps(collections, indent=2))

        except Exception as e:
            print(f"Error during retrieval: {e}")
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve STAC items from a STAC catalog.")
    parser.add_argument(
        "--stac-endpoint",
        required=False,
        help="STAC API endpoint URL. If not provided, will attempt to auto-discover from account.",
    )
    parser.add_argument("--item-id", required=False, help="Specific item ID to retrieve.")
    parser.add_argument("--collection-id", required=False, help="Collection ID to search within.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of items to return (default: 100).")
    parser.add_argument("--bbox", required=False, help="Bounding box filter in format 'minx,miny,maxx,maxy'.")
    parser.add_argument("--datetime", required=False, help="Datetime filter in format 'start/end'.")
    parser.add_argument("--token", required=False, help="Authorization token for the API.")
    parser.add_argument(
        "--region", required=False, default="us-west-2", help="AWS region to use for auto-discovery (default: us-west-2)."
    )
    parser.add_argument(
        "--export-name",
        required=False,
        default="DataCatalog-StacApiUrl",
        help="CloudFormation export name to search for (default: DataCatalog-StacApiUrl).",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.item_id and not args.collection_id:
        print("Error: --collection-id is required when specifying --item-id")
        sys.exit(1)

    # Auto-discover STAC endpoint if not provided
    stac_endpoint = args.stac_endpoint
    if not stac_endpoint:
        print(f"Auto-discovering STAC endpoint from CloudFormation export '{args.export_name}' in region '{args.region}'...")
        stac_endpoint = RetrieveCLI._discover_stac_endpoint(args.region, args.export_name)
        if not stac_endpoint:
            print(f"Error: Could not find CloudFormation export '{args.export_name}' in region '{args.region}'.")
            print("Please provide --stac-endpoint or ensure the export exists in your account.")
            sys.exit(1)
        print(f"Found STAC endpoint: {stac_endpoint}")

    retriever = RetrieveCLI(
        stac_endpoint=stac_endpoint,
        item_id=args.item_id,
        collection_id=args.collection_id,
        limit=args.limit,
        bbox=args.bbox,
        datetime=args.datetime,
        token=args.token,
    )

    retriever.run()
