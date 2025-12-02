# Copyright 2024-2025 Amazon.com, Inc. or its affiliates.

import asyncio
import json
from typing import Any, Dict

from stac_fastapi.opensearch.database_logic import DatabaseLogic, create_collection_index
from stac_fastapi.types.errors import NotFoundError
from stac_fastapi.types.stac import Collection, Item

from .managers import SNSManager
from .processor_base import ProcessorBase
from .stac_validator import StacValidationError, validate_stac_item
from .utils import AsyncContextFilter, ServiceConfig, get_minimal_collection_dict, logger


class IngestProcessor(ProcessorBase):
    """
    A class to process STAC items from an SNS event source, integrated with OpenSearch
    database logic from stac_fastapi.opensearch.database_logic.
    """

    def __init__(self, message: str):
        """
        Initialize the STACProcessor with an OpenSearch DatabaseLogic client.

        :param message: The incoming SNS request message.
        """
        self.database = DatabaseLogic()
        self.stac_item = Item(**json.loads(message))
        self.sns_manager = (
            SNSManager(ServiceConfig.stac_post_processing_topic) if ServiceConfig.stac_post_processing_topic else None
        )

    async def process(self) -> Dict[str, Any]:
        """
        Process the incoming SNS message, download and process the image, and publish the results.

        :returns: A response indicating the status of the process.
        """
        try:
            logger.info(self.stac_item)
            validate_stac_item(self.stac_item)
        except StacValidationError as err:
            return self.failure_message(f"Invalid STAC item: {err}")
        try:
            item_id = self.stac_item["id"]
            AsyncContextFilter.set_context({"item_id": item_id})
            collection_id = self.stac_item["collection"]
            logger.info(f"Creating STAC item in collection {collection_id}.")

            # Create a STAC item in the open search database.
            #  If the item collection does not exist, create a minimal one and then insert the item.
            try:
                await self.database.check_collection_exists(collection_id)
            except NotFoundError:
                logger.info(f"{collection_id} collection not found. Creating minimal collection.")
                await self.create_minimal_collection(collection_id)
            prepped_item = await self.database.async_prep_create_item(self.stac_item, "")
            logger.info(f"Prepped data: {prepped_item}")
            await self.database.create_item(prepped_item)

            # Add STAC items with asset title that matches one in POST_PROCESS_ASSET_DATA_TITLES
            #  to the post-processing topic, if present
            asset_data_title = self.stac_item.get("assets", {}).get("data", {}).get("title", None)
            if self.sns_manager and asset_data_title and asset_data_title in ServiceConfig.post_processing_asset_data_titles:
                self.sns_manager.publish_message(message=json.dumps(self.stac_item), subject=asset_data_title)

            # Return a success message
            return self.success_message("STAC item created successfully")
        except Exception as error:
            # Return a failure message with the stack trace
            return self.failure_message(error)

    async def create_minimal_collection(self, collection_id: str) -> None:
        # Ensure proper collection index exists with correct mapping (idempotent)
        await create_collection_index()
        # Create collection
        collection = Collection(**get_minimal_collection_dict(collection_id))
        await self.database.create_collection(collection)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    The AWS Lambda handler function to process an event.

    :param event: The event payload contains the SNS message.
    :param context: The Lambda execution context (unused).
    :return: The response from the IngestProcessor process.
    """
    # Log the event payload to see the raw SNS message
    message = event["Records"][0]["Sns"]["Message"]
    processor = IngestProcessor(message)

    async def process_with_cleanup():
        """Process the message and ensure database client is closed."""
        try:
            return await processor.process()
        finally:
            # Ensure the database client is properly closed to avoid unclosed session warnings
            if hasattr(processor.database, "client") and processor.database.client:
                await processor.database.client.close()

    return asyncio.run(process_with_cleanup())
