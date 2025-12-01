#  Copyright 2024-2025 Amazon.com, Inc. or its affiliates.

import argparse
import base64
import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional

import boto3


@dataclass
class APIGatewayEventBuilder:
    """Helper class to build API Gateway v1 events for Mangum."""

    root_path: str = "data-catalog"

    def build(
        self,
        path: str,
        method: str = "GET",
        query_params: Optional[Dict[str, str]] = None,
        path_params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Build an API Gateway v1 event."""
        full_path = f"/{self.root_path}{path}" if path.startswith("/") else f"/{self.root_path}/{path}"

        # Build query string
        filtered_params = {k: v for k, v in (query_params or {}).items() if v}
        query_string = "&".join(f"{k}={v}" for k, v in filtered_params.items())
        multi_value_params = {k: [v] for k, v in filtered_params.items()}

        return {
            "httpMethod": method,
            "path": full_path,
            "pathParameters": path_params,
            "queryStringParameters": filtered_params if filtered_params else None,
            "multiValueQueryStringParameters": multi_value_params if multi_value_params else None,
            "headers": {"Content-Type": "application/json", "Accept": "application/json"},
            "multiValueHeaders": {
                "Content-Type": ["application/json"],
                "Accept": ["application/json"],
            },
            "body": None,
            "isBase64Encoded": False,
            "requestContext": {
                "requestId": "cli-request",
                "stage": "default",
                "httpMethod": method,
                "path": full_path,
                "requestTime": "01/Jan/2024:00:00:00 +0000",
                "requestTimeEpoch": 1704067200,
                "identity": {"sourceIp": "127.0.0.1", "userAgent": "RetrieveCLI/1.0"},
                "apiId": "cli-api",
            },
            "resource": full_path,
            "queryString": query_string,
        }


class RetrieveCLI:
    def __init__(
        self,
        item_id: Optional[str] = None,
        collection_id: Optional[str] = None,
        limit: int = 100,
        bbox: Optional[str] = None,
        datetime: Optional[str] = None,
        lambda_function_name: str = "data-catalog-stac",
        lambda_region: str = "us-west-2",
        stac_root_path: str = "data-catalog",
    ) -> None:
        """Initialize the RetrieveCLI for Lambda-based STAC catalog access."""
        self.item_id = item_id
        self.collection_id = collection_id
        self.limit = limit
        self.bbox = bbox
        self.datetime = datetime
        self.stac_root_path = stac_root_path
        self.lambda_function_name = lambda_function_name
        self.lambda_client = boto3.client("lambda", region_name=lambda_region)
        self.event_builder = APIGatewayEventBuilder(root_path=stac_root_path)

    def _create_lambda_event(
        self, path: str, method: str = "GET", query_params: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create an API Gateway v1 event for Mangum handler."""
        # Extract path parameters
        path_parts = path.strip("/").split("/")
        path_params = None
        try:
            collections_idx = path_parts.index("collections")
            if len(path_parts) > collections_idx + 1:
                path_params = {"collection_id": path_parts[collections_idx + 1]}
                if len(path_parts) > collections_idx + 2 and path_parts[collections_idx + 2] == "items":
                    if len(path_parts) > collections_idx + 3:
                        path_params["item_id"] = path_parts[collections_idx + 3]
        except ValueError:
            pass  # No "collections" in path

        return self.event_builder.build(path, method, query_params, path_params)

    def _invoke_lambda(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the Lambda function and parse the response."""
        try:
            response = self.lambda_client.invoke(
                FunctionName=self.lambda_function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(event),
            )

            payload = json.loads(response["Payload"].read())

            if "errorMessage" in payload or "errorType" in payload:
                error_msg = payload.get("errorMessage", str(payload))
                raise Exception(f"Lambda invocation failed: {error_msg}")

            if "statusCode" not in payload:
                return payload

            status_code = payload["statusCode"]
            body_str = payload.get("body")

            if not body_str:
                if status_code >= 400:
                    raise Exception(f"HTTP {status_code}: Empty response body")
                return {}

            if isinstance(body_str, dict):
                return body_str

            if not isinstance(body_str, str) or not body_str.strip():
                if status_code >= 400:
                    raise Exception(f"HTTP {status_code}: Invalid response body")
                return {}

            # Decode base64 if needed (Mangum may encode responses)
            if payload.get("isBase64Encoded", False):
                body_str = base64.b64decode(body_str).decode("utf-8")
            else:
                # Try auto-detecting base64 (Mangum sometimes encodes without flag)
                try:
                    if len(body_str) > 20 and all(
                        c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for c in body_str
                    ):
                        decoded = base64.b64decode(body_str).decode("utf-8")
                        if decoded.strip().startswith(("{", "[")):
                            body_str = decoded
                except Exception:
                    pass

            body = json.loads(body_str)
            if status_code >= 400:
                raise Exception(f"HTTP {status_code}: {body}")

            return body

        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Lambda response: {e}")
        except Exception as e:
            raise Exception(f"Error invoking Lambda: {e}") from e

    def get_item(self, item_id: str, collection_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific STAC item by ID and collection."""
        try:
            event = self._create_lambda_event(f"/collections/{collection_id}/items/{item_id}")
            return self._invoke_lambda(event)
        except Exception as e:
            print(f"Error retrieving item: {e}")
            return None

    def search_items(self) -> Dict[str, Any]:
        """Search for STAC items using the provided filters."""
        try:
            query_params = {}
            if self.limit > 0:
                query_params["limit"] = str(self.limit)
            if self.bbox:
                query_params["bbox"] = self.bbox
            if self.datetime:
                query_params["datetime"] = self.datetime

            path = f"/collections/{self.collection_id}/items" if self.collection_id else "/search"
            event = self._create_lambda_event(path, query_params=query_params)
            return self._invoke_lambda(event)
        except Exception as e:
            print(f"Error searching items: {e}")
            return {"features": [], "type": "FeatureCollection"}

    def list_collections(self) -> Dict[str, Any]:
        """List all available collections."""
        try:
            query_params = {"limit": str(self.limit)} if self.limit else None
            event = self._create_lambda_event("/collections", query_params=query_params)
            return self._invoke_lambda(event)
        except Exception as e:
            print(f"Error listing collections: {e}")
            return {"collections": []}

    def get_collection(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific collection by ID."""
        try:
            event = self._create_lambda_event(f"/collections/{collection_id}")
            return self._invoke_lambda(event)
        except Exception as e:
            print(f"Error retrieving collection: {e}")
            return None

    def run(self) -> None:
        """Execute the main retrieval process based on provided parameters."""
        try:
            if self.item_id and self.collection_id:
                item = self.get_item(self.item_id, self.collection_id)
                if item:
                    print(json.dumps(item, indent=2))
                else:
                    sys.exit(1)
            elif self.collection_id:
                results = self.search_items()
                print(json.dumps(results, indent=2))
            else:
                collections = self.list_collections()
                print(json.dumps(collections, indent=2))
        except Exception as e:
            print(f"Error during retrieval: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve STAC items from a STAC catalog via Lambda invocation.")
    parser.add_argument("--item-id", help="Specific item ID to retrieve.")
    parser.add_argument("--collection-id", help="Collection ID to search within.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of items to return (default: 100).")
    parser.add_argument("--bbox", help="Bounding box filter in format 'minx,miny,maxx,maxy'.")
    parser.add_argument("--datetime", help="Datetime filter in format 'start/end'.")
    parser.add_argument(
        "--lambda-function-name",
        default="data-catalog-stac",
        help="Name of the Lambda function to invoke (default: data-catalog-stac).",
    )
    parser.add_argument(
        "--lambda-region",
        default="us-west-2",
        help="AWS region for Lambda invocation (default: us-west-2).",
    )
    parser.add_argument(
        "--stac-root-path",
        default="data-catalog",
        help="Root path for STAC API (default: data-catalog).",
    )

    args = parser.parse_args()

    if args.item_id and not args.collection_id:
        print("Error: --collection-id is required when specifying --item-id")
        sys.exit(1)

    try:
        retriever = RetrieveCLI(
            item_id=args.item_id,
            collection_id=args.collection_id,
            limit=args.limit,
            bbox=args.bbox,
            datetime=args.datetime,
            lambda_function_name=args.lambda_function_name,
            lambda_region=args.lambda_region,
            stac_root_path=args.stac_root_path,
        )
        retriever.run()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
