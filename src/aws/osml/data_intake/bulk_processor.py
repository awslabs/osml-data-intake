#  Copyright 2024-2025 Amazon.com, Inc. or its affiliates.

import asyncio
import json
import logging
import os
import sys
import traceback
from secrets import token_hex
from typing import List, Optional, Tuple

import boto3
from boto3.resources.base import ServiceResource
from botocore.exceptions import ClientError
from stac_fastapi.opensearch.database_logic import DatabaseLogic
from stac_fastapi.types.errors import NotFoundError
from stac_fastapi.types.stac import Collection, Item

from aws.osml.data_intake.image_processor import ImageData
from aws.osml.data_intake.managers.s3_manager import S3Manager, S3Url
from aws.osml.data_intake.managers.sns_manager import SNSRequest
from aws.osml.data_intake.utils import AsyncContextFilter, BotoConfig, ServiceConfig, get_minimal_collection_dict, logger


class BulkProcessor:
    def __init__(
        self,
        aws_s3: ServiceResource,
        output_path: str,
        output_bucket: str,
        stac_endpoint: str,
        collection_id: str,
        input_path: str,
    ) -> None:
        """
        Initializes the BulkProcessor class.

        :param aws_s3: The AWS S3 client object.
        :param output_path: The output path for storing processed data.
        :param output_bucket: The output bucket for storing processed data.
        :param stac_endpoint: The URL of the STAC endpoint.
        :param collection_id: The ID of the STAC collection.
        :param input_path: The input path for storing original data.
        """
        self.aws_s3 = aws_s3
        self.collection_id = collection_id
        self.output_bucket = output_bucket
        self.input_path = input_path
        self.output_path = output_path
        self.stac_endpoint = stac_endpoint
        self.database = DatabaseLogic()
        self.failed_manifest_path = os.path.join(self.output_path, "failed_images_manifest.json")

    def generate_upload_files(self, image: str, image_id: str) -> Tuple[ImageData, S3Manager, Optional[str]]:
        """
        Generate required files for the given image, upload generated files, and then delete
        the files once uploaded.

        :param image: Path or S3 URL of the image.
        :param image_id: ID of the image.

        :return Tuple containing ImageData, S3Manager instance, and ovr_file path (if generated, else None).
        """

        AsyncContextFilter.set_context({"item_id": image_id})

        s3_url = S3Url(image)
        s3_manager = S3Manager(self.output_bucket, self.aws_s3, f"{self.input_path}/{image_id}")

        # set the output folder to the id
        s3_manager.set_output_folder(image_id)

        local_object_path = s3_manager.download_file(s3_url)
        image_data = ImageData(local_object_path)

        aux_file = image_data.generate_aux_file()
        s3_manager.upload_file(aux_file, ".AUX")

        ovr_file = image_data.generate_ovr_file()
        if ovr_file:
            s3_manager.upload_file(ovr_file, ".OVR")

        # list files in the directory
        listDir = os.listdir(s3_manager.tmp_dir)
        logger.info(f"Files in the directory (generateFiles): {listDir}")

        # Delete files then clean up dataset to preserve storage space
        files_to_delete = [local_object_path, aux_file]
        if ovr_file:
            files_to_delete.append(ovr_file)
        image_data.delete_files(files_to_delete)
        image_data.clean_dataset()

        return image_data, s3_manager, ovr_file

    def record_failed_image(self, error_details: dict) -> None:
        """
        Record details of failed image processing in a manifest file.

        :param error_details: Dictionary containing details of the failed image and error.

        :return None
        """
        try:
            with open(self.failed_manifest_path, "a") as manifest_file:
                json.dump(error_details, manifest_file)
                manifest_file.write("\n")
            logger.info(f"Failed image details recorded in {self.failed_manifest_path}.")
        except Exception as e:
            logger.error(f"Failed to record failed image details in {self.failed_manifest_path}: {e}")

    async def process_image(self, image: str, semaphore: asyncio.Semaphore) -> Optional[Item]:
        """
        Process a single image

        :param image: Path or S3 URL of the image.
        :param semaphore: Semaphore for limiting concurrent workers.

        :return STAC item if successful, None otherwise.
        """
        async with semaphore:
            try:
                image_id = token_hex(16)
                image_data, s3_manager, ovr_file = self.generate_upload_files(image, image_id)
                logger.info(f"Creating STAC item with ID {image_id}")
                # Create SNSRequest object for generate_stac_item
                request = SNSRequest(image_uri=image, item_id=image_id, collection_id=self.collection_id)
                # ovr_file is generated and uploaded in generate_upload_files, but then deleted
                # Pass the path if it was generated (for asset inclusion), even though file is deleted
                stac_item = image_data.generate_stac_item(s3_manager, request, ovr_file)
                return stac_item
            except Exception as error:
                error_details = {"image": image, "error": str(error), "internal_traceback": traceback.format_exc()}
                logger.error(f"Failed to process image - {error_details}")
                self.record_failed_image(error_details)
                return None

    def submit_bulk_data_catalog(self, collection_id: str, stac_items: List[Item]) -> None:
        """
        Submit the data catalog to the STAC endpoint

        :param collection_id: The ID of the STAC collection.
        :param stac_items: List of STAC items to be submitted.

        :return None
        """
        try:
            AsyncContextFilter.set_context({"image_hash": None})
            # Insert the STAC Items
            self.database.bulk_sync(collection_id, stac_items)
            logger.info(f"Successfully bulk inserted {len(stac_items)} item(s) to the {collection_id} collection!")
        except Exception as error:
            logger.error(f"Unable to submit data catalog item... {error} / {traceback.format_exc()}")
            raise Exception(f"Unable to submit data catalog item... {error}")

    async def create_minimal_collection(self, collection_id: str) -> None:
        collection = Collection(**get_minimal_collection_dict(collection_id))
        await self.database.create_collection(collection)


async def start_workers(image_batch: List[str], bulk_processor: BulkProcessor, max_workers: int) -> None:
    """
    Starts worker tasks to process a batch of images.

    :param image_batch: A list of image paths or S3 URLs.
    :param bulk_processor: An instance of the BulkProcessor class.
    :param max_workers: The maximum number of concurrent workers.

    :return None
    """
    semaphore = asyncio.Semaphore(max_workers)
    stac_items = []
    queue = asyncio.Queue()

    # If the collection does not exist, create a minimal one.
    try:
        await bulk_processor.database.check_collection_exists(bulk_processor.collection_id)
    except NotFoundError:
        logger.info(f"{bulk_processor.collection_id} collection not found. Creating minimal collection.")
        await bulk_processor.create_minimal_collection(bulk_processor.collection_id)

    async def worker():
        while True:
            image = await queue.get()
            if image is None:
                break
            stac_item = await bulk_processor.process_image(image, semaphore)
            if stac_item:
                stac_items.append(stac_item)
                if len(stac_items) >= 5:
                    bulk_processor.submit_bulk_data_catalog(bulk_processor.collection_id, stac_items)
                    stac_items.clear()
            queue.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(max_workers)]

    for image in image_batch:
        await queue.put(image)

    await queue.join()

    for _ in range(max_workers):
        await queue.put(None)

    # Ensure all workers are stopped
    await asyncio.gather(*workers)

    # Insert any remaining items to STAC catalog
    if stac_items:
        bulk_processor.submit_bulk_data_catalog(bulk_processor.collection_id, stac_items)

    logger.info("All images processed.")


def process_manifest_file(aws_s3: ServiceResource, input_path: str, s3_uri: str) -> Optional[List[str]]:
    """
    Processes a manifest file containing a list of S3 object paths.

    :param aws_s3: The AWS S3 client object.
    :param input_path: The local path where the manifest file will be downloaded.
    :param s3_uri: The S3 URI of the manifest file.

    :return: A list of S3 object paths if the manifest file exists, otherwise None.
    """
    s3_url = S3Url(s3_uri)
    local_json_path = f"{input_path}/{s3_url.key}"
    aws_s3.meta.client.download_file(s3_url.bucket, s3_url.key, local_json_path)

    with open(local_json_path, "r", encoding="utf-8") as manifest_file:
        manifest_data = json.load(manifest_file)

        if manifest_data:
            s3_list = []
            for entry in manifest_data:
                s3_list.append(entry["S3Uri"])

            logger.info(f"Total of {len(s3_list)} files in the manifest.")
            logger.debug(f"Here is the list of it: {s3_list}.")
            return s3_list
        else:
            return None


async def main() -> None:
    """
    This function is responsible for orchestrating the data intake process. It retrieves the necessary
    environment variables, initializes the AWS S3 resource, processes the manifest file, generate
    ovr/aux, create STAC item, and publish to the Database Cluster

    :returns: None
    """

    if ServiceConfig.bulk_enable_debugging:
        logger.setLevel(logging.DEBUG)

    try:
        aws_s3 = boto3.resource("s3", config=BotoConfig.default)
    except ClientError as err:
        sys.exit(f"Fatal error occurred while initializing AWS services. Exiting. {err}")

    if ServiceConfig.bulk_input_path:
        s3_list = process_manifest_file(aws_s3, ServiceConfig.bulk_input_path, ServiceConfig.bulk_s3_uri)
        bulk_processor = BulkProcessor(
            aws_s3,
            ServiceConfig.bulk_output_path,
            ServiceConfig.bulk_output_bucket,
            ServiceConfig.bulk_stac_endpoint,
            ServiceConfig.bulk_collection_id,
            ServiceConfig.bulk_input_path,
        )
        if s3_list:
            await start_workers(s3_list, bulk_processor, ServiceConfig.bulk_max_workers)
            await bulk_processor.database.client.close()
        else:
            logger.error("The manifest file is empty or not found.")
    else:
        logger.error("The environment variable S3_INPUT_PATH is not set.")
        raise ValueError("The environment variable S3_INPUT_PATH is not set.")


if __name__ == "__main__":
    asyncio.run(main())
