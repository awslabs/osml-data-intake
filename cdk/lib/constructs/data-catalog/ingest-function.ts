/*
 * Copyright 2024-2025 Amazon.com, Inc. or its affiliates.
 */

import { Duration, RemovalPolicy, Size } from "aws-cdk-lib";
import {
  ISecurityGroup,
  IVpc,
  Port,
  SubnetSelection
} from "aws-cdk-lib/aws-ec2";
import { IRole, Role } from "aws-cdk-lib/aws-iam";
import {
  DockerImageFunction,
  Function,
  LoggingFormat
} from "aws-cdk-lib/aws-lambda";
import { CfnLogGroup } from "aws-cdk-lib/aws-logs";
import { Domain } from "aws-cdk-lib/aws-opensearchservice";
import { ITopic } from "aws-cdk-lib/aws-sns";
import { LambdaSubscription } from "aws-cdk-lib/aws-sns-subscriptions";
import { Construct } from "constructs";

import { OSMLAccount } from "../types";
import { Container, ContainerConfig } from "./container";
import { DataplaneConfig } from "./dataplane";
import { IngestRole } from "./ingest-role";

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
  /** The OpenSearch domain. */
  readonly osDomain: Domain;
  /** The ingest SNS topic. */
  readonly ingestTopic: ITopic;
  /** The security group for the Lambda function (optional). */
  readonly securityGroup?: ISecurityGroup;
  /** The DC dataplane configuration. */
  readonly config: DataplaneConfig;
  /** The removal policy for resources. */
  readonly removalPolicy: RemovalPolicy;
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
  /** The IAM role for the Lambda function. */
  public readonly role: IRole;
  /** The container for the Lambda function. */
  public readonly container: Container;

  /**
   * Creates a new IngestFunction construct.
   *
   * @param scope - The scope/stack in which to define this construct
   * @param id - The id of this construct within the current scope
   * @param props - The properties for configuring this construct
   */
  constructor(scope: Construct, id: string, props: IngestFunctionProps) {
    super(scope, id);

    // Initialize the Lambda role
    this.role = this.initializeRole(props);

    // Create the ingest container
    this.container = this.createContainer(props);

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
      code: this.container.dockerImageCode,
      role: this.role,
      vpc: props.vpc,
      vpcSubnets: props.selectedSubnets,
      timeout: Duration.seconds(props.config.INGEST_LAMBDA_TIMEOUT),
      ephemeralStorageSize: Size.gibibytes(
        props.config.INGEST_LAMBDA_STORAGE_SIZE
      ),
      memorySize: props.config.INGEST_LAMBDA_MEMORY_SIZE,
      environment: env,
      securityGroups: props.securityGroup ? [props.securityGroup] : [],
      loggingFormat: LoggingFormat.JSON
    });
    this.function.node.addDependency(this.container);

    // Set removal policy on the automatically created log group
    if (this.function.logGroup) {
      const logGroupResource = this.function.logGroup.node
        .defaultChild as CfnLogGroup;
      if (logGroupResource) {
        logGroupResource.applyRemovalPolicy(props.removalPolicy);
      }
    }

    // Subscribe Lambda function to the SNS topic
    props.ingestTopic.addSubscription(new LambdaSubscription(this.function));

    // Allow the ingest Lambda to connect to OpenSearch
    props.osDomain.connections.allowFrom(this.function, Port.tcp(443));
  }

  /**
   * Initializes the ingest Lambda role.
   *
   * @param props - The IngestFunction properties
   * @returns The ingest Lambda role
   */
  private initializeRole(props: IngestFunctionProps): IRole {
    if (
      props.config.INGEST_LAMBDA_ROLE_NAME &&
      props.config.INGEST_LAMBDA_ROLE_NAME !== undefined &&
      props.config.INGEST_LAMBDA_ROLE_NAME !== ""
    ) {
      return Role.fromRoleName(
        this,
        "ImportedIngestFunctionRole",
        props.config.INGEST_LAMBDA_ROLE_NAME,
        { mutable: false }
      );
    }
    return new IngestRole(this, "IngestFunctionRole", {
      account: props.account,
      roleName: "IngestFunctionRole"
    }).role;
  }

  /**
   * Creates the ingest container.
   *
   * @param props - The IngestFunction properties
   * @returns The ingest container
   */
  private createContainer(props: IngestFunctionProps): Container {
    return new Container(this, "IngestContainer", {
      account: props.account,
      buildDockerImageCode: true,
      buildFromSource: props.config.BUILD_FROM_SOURCE,
      config: new ContainerConfig({
        CONTAINER_URI: props.config.INGEST_CONTAINER_URI,
        CONTAINER_BUILD_PATH: props.config.CONTAINER_BUILD_PATH,
        CONTAINER_BUILD_TARGET: props.config.INGEST_CONTAINER_BUILD_TARGET,
        CONTAINER_DOCKERFILE: props.config.INGEST_CONTAINER_DOCKERFILE
      })
    });
  }
}
