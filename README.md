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
* [Test Locally](#test-locally)
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

**Run the Test Command:**

1. Replace the following with your specific details: \
  **Topic ARN**: Update the `--topic-arn` argument with the ARN of the SNS topic that triggers your application.\
  **S3 URL**: Replace the S3 URL in the `--s3-uri` argument with the URL of the bucket or image file you want to test.\
  **Item ID**: Required `--item-id` parameter that sets the ID of the item.\
  **Collection ID**: Optional `--collection-id` parameter that also adds a collection ID to the item. Defaults to `OSML`.\
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
   python3 bin/stream/retrieve_cli.py --item-id <DESIRED_ITEM_ID> --collection-id <COLLECTION_ID>
   ```

   To list all collections:

   ```bash
   python3 bin/stream/retrieve_cli.py
   ```

   To search for items in a collection:

   ```bash
   python3 bin/stream/retrieve_cli.py --collection-id <COLLECTION_ID>
   ```

   **Note:** The retrieve CLI uses Lambda invocation to access the STAC catalog. By default, it uses the `data-catalog-stac` Lambda function in `us-west-2`. You can customize this with `--lambda-function-name` and `--lambda-region` if needed.

## Running Integration Tests

The integration test is a Lambda function that performs an end-to-end smoke test of the data catalog pipeline. It:

1. Uploads a test image to S3
2. Publishes to the intake SNS topic
3. Waits for processing
4. Retrieves the item from the STAC catalog
5. Validates it was added correctly

**Prerequisites:**

* Ensure that your AWS credentials are configured properly in the environment
* Deploy the integration test stack by setting `"deployIntegrationTests": true` in your `cdk/bin/deployment/deployment.json`
* Deploy the CDK stacks including the integration test stack

**Run the Integration Test:**

1. Run the integration test using pytest:

   ```bash
   pytest test/integ/test_integration.py
   ```

2. By default, it invokes the `data-catalog-integration-test` Lambda function in `us-west-2`. You can configure the Lambda function name and region via environment variables:

   ```bash
   INTEG_TEST_LAMBDA_FUNCTION_NAME=<FUNCTION_NAME> INTEG_TEST_LAMBDA_REGION=<REGION> pytest test/integ/test_integration.py
   ```

3. The test will output the results, including:
   * Success/failure status
   * Test item ID
   * Elapsed time
   * Any errors encountered

**Note:** The integration test Lambda function must be deployed and configured with the appropriate environment variables (INPUT_BUCKET, INPUT_TOPIC_ARN, STAC_FUNCTION_NAME, etc.) which are automatically set by the CDK stack.

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

This library is licensed under the Apache 2.0 License. See [LICENSE](https://github.com/aws-solutions-library-samples/osml-data-intake/LICENSE).
