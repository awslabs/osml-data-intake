/*
 * Copyright 2024-2025 Amazon.com, Inc. or its affiliates.
 */

import { Duration, Size } from "aws-cdk-lib";
import { IVpc, Port, SubnetSelection } from "aws-cdk-lib/aws-ec2";
import { IRole } from "aws-cdk-lib/aws-iam";
import {
  DockerImageFunction,
  Function,
  LoggingFormat
} from "aws-cdk-lib/aws-lambda";
import { Domain } from "aws-cdk-lib/aws-opensearchservice";
import { ITopic } from "aws-cdk-lib/aws-sns";
import { LambdaSubscription } from "aws-cdk-lib/aws-sns-subscriptions";
import { Construct } from "constructs";

import { OSMLAccount } from "../types";
import { Container } from "./container";
import { DataplaneConfig } from "./dataplane";

/**
 * Properties for creating the ingest Lambda function.
 */
export interface IngestFunctionProps {
  /** The OSML account configuration. */
  readonly account: OSMLAccount;
  /** The VPC configuration. */
  readonly vpc: IVpc;
  /** The selected subnets for the VPC. */
  readonly selectedSubnets: SubnetSelection;
  /** The IAM role for the Lambda function. */
  readonly lambdaRole: IRole;
  /** The ingest container. */
  readonly ingestContainer: Container;
  /** The OpenSearch domain. */
  readonly osDomain: Domain;
  /** The ingest SNS topic. */
  readonly ingestTopic: ITopic;
  /** The DC dataplane configuration. */
  readonly config: DataplaneConfig;
}

/**
 * Construct that manages the ingest Lambda function for the Data Catalog.
 *
 * This construct encapsulates the creation and configuration of the Lambda
 * function for ingesting STAC items.
 */
export class IngestFunction extends Construct {
  /** The Lambda function for ingesting STAC items. */
  public readonly function: Function;

  /**
   * Creates a new IngestFunction construct.
   *
   * @param scope - The scope/stack in which to define this construct
   * @param id - The id of this construct within the current scope
   * @param props - The properties for configuring this construct
   */
  constructor(scope: Construct, id: string, props: IngestFunctionProps) {
    super(scope, id);

    // Create an operating ENV for our lambda container
    const env = {
      STAC_FASTAPI_TITLE: props.config.STAC_FASTAPI_TITLE,
      STAC_FASTAPI_DESCRIPTION: props.config.STAC_FASTAPI_DESCRIPTION,
      STAC_FASTAPI_VERSION: props.config.STAC_FASTAPI_VERSION,
      RELOAD: props.config.STAC_RELOAD,
      ENVIRONMENT: props.config.STAC_ENVIRONMENT,
      WEB_CONCURRENCY: props.config.STAC_WEB_CONCURRENCY,
      ES_HOST: props.osDomain.domainEndpoint,
      ES_PORT: props.config.STAC_ES_PORT,
      ES_USE_SSL: props.config.STAC_ES_USE_SSL,
      ES_VERIFY_CERTS: props.config.STAC_ES_VERIFY_CERTS,
      STAC_FASTAPI_ROOT_PATH: `/${props.config.STAC_FASTAPI_ROOT_PATH}`
    };

    // Create the ingest Lambda function
    this.function = new DockerImageFunction(this, "DataCatalogIngestFunction", {
      functionName: "data-catalog-ingest",
      code: props.ingestContainer.dockerImageCode,
      role: props.lambdaRole,
      vpc: props.vpc,
      timeout: Duration.seconds(props.config.LAMBDA_TIMEOUT),
      ephemeralStorageSize: Size.gibibytes(props.config.LAMBDA_STORAGE_SIZE),
      memorySize: props.config.LAMBDA_MEMORY_SIZE,
      environment: env,
      loggingFormat: LoggingFormat.JSON
    });
    this.function.node.addDependency(props.ingestContainer);

    // Subscribe Lambda function to the SNS topic
    props.ingestTopic.addSubscription(new LambdaSubscription(this.function));

    // Allow the ingest Lambda to connect to OpenSearch
    props.osDomain.connections.allowFrom(this.function, Port.tcp(443));
  }
}
