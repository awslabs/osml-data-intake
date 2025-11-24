# OSML Data Intake

## Overview

This application facilitates the processing, conversion, and management of satellite imagery metadata as part of the
OversightML (OSML) framework and can be deployed as part of the
OSML [guidance package](https://github.com/aws-solutions-library-samples/guidance-for-processing-overhead-imagery-on-aws).
It leverages the GDAL library and integrates with Amazon S3 for seamless storage and sharing to provide imagery
metadata to other service components.
Below is an overview of the main features:

### Intake

The intake processes metadata from satellite imagery files, such as image dimensions and geographical coordinates.
Uploads auxiliary files and metadata to Amazon S3 and serves converted meta-data into STAC items on an SNS topic.

### Ingest

Ingests SpatioTemporal Asset Catalog (STAC) items placed on an SNS topic into via the STAC Fast API database logic.

### STAC

The STAC component powers a Fast API front end that allows for interacting with the OpenSearch database that houses
the processed geospatial assets.

### Table of Contents

* [Getting Started](#getting-started)
  * [Prerequisites](#prerequisites)
  * [Installation Guide](#installation-guide)
  * [Documentation](#documentation)
* [Test Locally](#testing-locally)
  * [Test Data Intake](#testing-data-intake)
  * [Test Data Catalog](#testing-data-catalog)
* [Submitting a Bulk Ingest Job](#submitting-a-bulk-ingest-job)
* [Support & Feedback](#support--feedback)
* [Security](#security)
* [License](#license)

## Getting Started

### Prerequisites

First, ensure you have installed the following tools locally

1. [aws cli](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)
2. [docker](https://nodejs.org/en)
3. [tox](https://tox.wiki/en/latest/installation.html)

### Installation Guide

1. Clone `osml-data-intake` package into your desktop

```sh
git clone https://github.com/aws-solutions-library-samples/osml-data-intake.git
```

1. Run `tox` to create a virtual environment

```sh
cd osml-data-intake
tox
```

### Documentation

You can find documentation for this library in the `./doc` directory. Sphinx is used to construct a searchable HTML
version of the API documents.

```shell
tox -e docs
```

## Test Locally

After setting up your environment, you can verify your setup by sending a test message to the SNS topic that will trigger your application workflow. This is useful for ensuring that your processing pipeline works correctly with a given image.

**Prerequisites:**

* Ensure that your AWS credentials are configured properly in the environment.
* Make sure that you have the AWS CLI installed and configured.
* Deploy the osml-data-intake infrastructure using the [guidance package](https://github.com/aws-solutions-library-samples/guidance-for-processing-overhead-imagery-on-aws)

### Test Data Intake

**Run the Test Command:**

1. Replace the following with your specific details: \
  **Topic ARN**: Update the `--topic-arn` argument with the ARN of the SNS topic that triggers your application.\
  **S3 URL**: Replace the S3 URL in the `--s3-uri` argument with the URL of the bucket or image file you want to test.\
  **Item ID**: Required `--item-id` parameter that sets the ID of the item.\
  **Collection ID**: Optional `--collection-id` parameter that also adds a collection ID to the item.  Defaults to `OSML`.\
  **Tile Server URL**: Optional `--tile-server-url` parameter for the URL to an OSML Tile Server, which will facilitate map tile creation.

2. An example command demonstrating the required parameters, substituting your actual values:

    ```bash
    python3 bin/stream/stream_cli.py --topic-arn <YOUR_TOPIC_ARN> --s3-uri <YOUR_S3_URI> --item-id <DESIRED_ITEM_ID>
    ```

3. Validate Expected Output:\
  This will trigger the processing of the specified image file in your application.
  Verify that the auxiliary files are generated and uploaded to your configured S3 bucket,
  and ensure that the logs indicate a successful run.

4. Verify the item was ingested into your STAC catalog using the retrieve CLI:

   To retrieve a specific item:

   ```bash
   python3 bin/stream/retrieve_cli.py --stac-endpoint <YOUR_STAC_ENDPOINT> --item-id <DESIRED_ITEM_ID> --collection-id <COLLECTION_ID>
   ```

   To list all collections:

   ```bash
   python3 bin/stream/retrieve_cli.py --stac-endpoint <YOUR_STAC_ENDPOINT>
   ```

   To search for items in a collection:

   ```bash
   python3 bin/stream/retrieve_cli.py --stac-endpoint <YOUR_STAC_ENDPOINT> --collection-id <COLLECTION_ID>
   ```

### Test Data Catalog

1. To put a test item directly in your STAC catalog, update the following command and run it with your endpoint.
   **Note:** The STAC API requires items to be posted to `/collections/{collection_id}/items`, not `/collections`.

    ```bash
    curl -X "POST" "<YOUR_STAC_ENDPOINT>/collections/example-collection-3/items" \
         -H 'Content-Type: application/json; charset=utf-8' \
         -d '{
      "type": "Feature",
      "stac_version": "1.0.0",
      "id": "example-item",
      "properties": {
        "datetime": "2024-06-01T00:00:00Z",
        "start_datetime": "2024-06-01T00:00:00Z",
        "end_datetime": "2024-06-01T01:00:00Z"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [-104.99404, 39.75621],
            [-104.99404, 39.74575],
            [-104.97342, 39.74575],
            [-104.97342, 39.75621],
            [-104.99404, 39.75621]
          ]
        ]
      },
      "links": [
        {
          "rel": "self",
          "href": "http://example.com/catalog/example-item.json",
          "type": "application/json"
        },
        {
          "rel": "root",
          "href": "http://example.com/catalog/catalog.json",
          "type": "application/json"
        }
      ],
      "assets": {
        "thumbnail": {
          "href": "http://example.com/thumbs/example-item.jpg",
          "title": "Thumbnail",
          "type": "image/jpeg"
        },
        "data": {
          "href": "http://example.com/data/example-item.tif",
          "title": "Geospatial Data",
          "type": "image/tiff; application=geotiff"
        }
      },
      "collection": "example-collection-3"
    }'
    ```

2. To retrieve your item using the retrieve CLI:

   ```bash
   python3 bin/stream/retrieve_cli.py --stac-endpoint <YOUR_STAC_ENDPOINT> --item-id example-item --collection-id example-collection-3
   ```

   Or to list all collections:

   ```bash
   python3 bin/stream/retrieve_cli.py --stac-endpoint <YOUR_STAC_ENDPOINT>
   ```

   **Note:** Replace `<YOUR_STAC_ENDPOINT>` with your actual STAC API endpoint URL (e.g., `https://bfa9gemm4l.execute-api.us-west-2.amazonaws.com/data-catalog`).

## Submitting a Bulk Ingest Job

This workflow is tailored for efficiently processing large quantities of images stored in an S3 bucket and integrating them into a STAC catalog using AWS services. It is designed to streamline the ingestion process for thousands of images awaiting cataloging.

**Prerequisites:**

* Ensure AWS credentials are correctly configured.
* Install and configure the AWS CLI.
* Active STAC Catalog service.
* S3 Input and Output Buckets configured.

1. Build and push a Docker container to your ECR repository:

```bash
./scripts/build_upload_container.sh
```

1. Create an execution role using the following command:

```bash
aws iam create-role \
    --role-name BulkIngestSageMakerExecutionRole \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": ["sagemaker.amazonaws.com", "opensearchservice.amazonaws.com"]
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }' \
    --description "Allows SageMaker to execute processing jobs and specific S3 actions." \
    && aws iam attach-role-policy \
        --role-name BulkIngestSageMakerExecutionRole \
        --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess \
    && aws iam attach-role-policy \
        --role-name BulkIngestSageMakerExecutionRole \
        --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess
```

Retrieve the full ARN of the custom SageMaker role:

```bash
aws iam get-role --role-name BulkIngestSageMakerExecutionRole --query 'Role.Arn' --output text
```

1. Head over to Bulk Configuration [README.md](bin/bulk/config/README.md) on configuring your bulk job

1. Execute the SageMaker Processing Job:

    ```bash
    python3 ./bin/bulk/bulk_cli.py \
        --s3-uri <S3 Input Bucket> \
        --region <AWS Region> \
        --output-bucket <S3 Output Bucket>
    ```

    **Example command:**

    ```bash
    python3 ./bin/bulk/bulk_cli.py \
        --s3-uri s3://test-images-bucket \
        --region us-west-2 \
        --output-bucket s3://<id>-output-bucket
    ```

1. To monitor the ProcessingJob status, there are two ways:
   * Navigate to the SageMaker Processing Console: AWS -> SageMaker -> Processing (Left Sidebar) -> Processing Job, and monitor it there.

   * Alternatively, monitor using the command:

    ```bash
    python3 bin/bulk/check_job.py --region us-west-2 [--job name]
    ```

    **Note:** Replace [--job name] with your specific job name if needed.

1. Cleanup when completed:

    * Delete Bulk Ingest Container

        ```bash
        aws ecr batch-delete-image --repository-name data-bulk-ingest-container --image-ids "$(aws ecr describe-images --repository-name data-bulk-ingest-container --query 'imageIds[*]' --output json)"

        aws ecr delete-repository --repository-name data-bulk-ingest-container --force
        ```

    * Delete Custom Execution Role ARN

        ```bash
        aws iam delete-role --role-name BulkIngestSageMakerExecutionRole
        ```

## Support & Feedback

To post feedback, submit feature ideas, or report bugs, please use the [Issues](https://github.com/aws-solutions-library-samples/osml-data-intake/issues) section of this GitHub repo.

If you are interested in contributing to OversightML Data Intake, see the [CONTRIBUTING](https://github.com/aws-solutions-library-samples/osml-data-intake/CONTRIBUTING.md) guide.

## Security

See [CONTRIBUTING](https://github.com/aws-solutions-library-samples/osml-data-intake/CONTRIBUTING.md) for more information.

## License

MIT No Attribution Licensed. See [LICENSE](https://github.com/aws-solutions-library-samples/osml-data-intake/LICENSE).
