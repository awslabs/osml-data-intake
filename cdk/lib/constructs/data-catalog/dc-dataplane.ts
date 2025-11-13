/*
 * Copyright 2023-2025 Amazon.com, Inc. or its affiliates.
 */

import { Duration, RemovalPolicy, Size } from "aws-cdk-lib";
import { ISecurityGroup, Port, SecurityGroup } from "aws-cdk-lib/aws-ec2";
import { IRole, Role } from "aws-cdk-lib/aws-iam";
import { DockerImageFunction } from "aws-cdk-lib/aws-lambda";
import { ITopic, Topic } from "aws-cdk-lib/aws-sns";
import { LambdaSubscription } from "aws-cdk-lib/aws-sns-subscriptions";
import { Construct } from "constructs";

import { Container } from "../shared/osml-container";
import { OSMLVpc } from "../shared/osml-vpc";
import { BaseConfig, ConfigType, OSMLAccount } from "../types";
import { DCOpenSearchDomain } from "./dc-opensearch-domain";
import { DCLambdaRole } from "./roles/dc-lambda-role";

/**
 * Configuration class for DCDataplane Construct.
 */
export class DCDataplaneConfig extends BaseConfig {
  /**
   * Whether to build container resources from source.
   * @default "false"
   */
  public BUILD_FROM_SOURCE: boolean;

  /**
   * The build path for the Data Catalog.
   * @default "lib/osml-data-intake"
   */
  public CONTAINER_BUILD_PATH: string;

  /**
   * The build target for the Data Catalog STAC function.
   * @default "stac"
   */
  public CONTAINER_BUILD_TARGET_STAC: string;

  /**
   * The build target for the Data Catalog ingest function.
   * @default "ingest"
   */
  public CONTAINER_BUILD_TARGET_INGEST: string;

  /**
   * The relative Dockerfile to use to build the STAC container.
   * @default "docker/Dockerfile.stac"
   */
  public CONTAINER_DOCKERFILE_STAC: string;

  /**
   * The relative Dockerfile to use to build the ingest container.
   * @default "docker/Dockerfile.ingest"
   */
  public CONTAINER_DOCKERFILE_INGEST: string;

  /**
   * The container image to use for the STAC lambda.
   * @default "awsosml/osml-data-intake-stac:latest"
   */
  public CONTAINER_URI_STAC: string;

  /**
   * The container image to use for the ingest lambda.
   * @default "awsosml/osml-data-intake-ingest:latest"
   */
  public CONTAINER_URI_INGEST: string;

  /**
   * The name of the STAC Lambda function.
   * @default "DataCatalogStacFunction"
   */
  public LAMBDA_STAC_FUNCTION_NAME: string;

  /**
   * The name of the ingest Lambda function.
   * @default "DataCatalogIngestFunction"
   */
  public LAMBDA_INGEST_FUNCTION_NAME: string;

  /**
   * The memory in MB to give the lambda runtime.
   * @default 1024
   */
  public LAMBDA_MEMORY_SIZE: number;

  /**
   * The timeout, in seconds, for the Lambda function.
   * @default 900
   */
  public LAMBDA_TIMEOUT: number;

  /**
   * The name to give the input SNS topic.
   * @default "data-catalog-ingest"
   */
  public SNS_INPUT_TOPIC_NAME: string;

  /**
   * Constructor for DCDataplane Construct.
   * @param config - The configuration object for DCDataplane.
   */
  constructor(config: ConfigType = {}) {
    super({
      BUILD_FROM_SOURCE: false,
      CONTAINER_BUILD_PATH: "lib/osml-data-intake",
      CONTAINER_BUILD_TARGET_STAC: "stac",
      CONTAINER_BUILD_TARGET_INGEST: "ingest",
      CONTAINER_DOCKERFILE_STAC: "docker/Dockerfile.stac",
      CONTAINER_DOCKERFILE_INGEST: "docker/Dockerfile.ingest",
      CONTAINER_URI_STAC: "awsosml/osml-data-intake-stac:latest",
      CONTAINER_URI_INGEST: "awsosml/osml-data-intake-ingest:latest",
      LAMBDA_STAC_FUNCTION_NAME: "DataCatalogStacFunction",
      LAMBDA_INGEST_FUNCTION_NAME: "DataCatalogIngestFunction",
      LAMBDA_MEMORY_SIZE: 1024,
      LAMBDA_TIMEOUT: 900,
      SNS_INPUT_TOPIC_NAME: "data-catalog-ingest",
      ...config
    });
  }
}

/**
 * Interface representing properties for configuring the DCDataplane Construct.
 */
export interface DCDataplaneProps {
  /**
   * The deployment account.
   * @type {Account}
   */
  account: OSMLAccount;

  /**
   * The VPC (Virtual Private Cloud) configuration for the Dataplane.
   * @type {OSMLVpc}
   */
  vpc: OSMLVpc;

  /**
   * The input topic to receive Data Catalog requests (optional).
   * @type {Topic | undefined}
   */
  inputTopic?: ITopic;

  /**
   * Custom configuration for the DCDataplane Construct (optional).
   * @type {DCDataplaneConfig | undefined}
   */
  config?: DCDataplaneConfig;
}

/**
 * Represents the DCDataplane construct responsible for managing the data catalog
 * resources including OpenSearch domain, Lambda functions for STAC processing,
 * and associated infrastructure.
 */
export class DCDataplane extends Construct {
  /**
   * The configuration for the DCDataplane.
   */
  public config: DCDataplaneConfig;

  /**
   * The STAC Lambda function for data catalog processing.
   */
  public stacLambdaFunction: DockerImageFunction;

  /**
   * The ingest Lambda function for data catalog processing.
   */
  public ingestLambdaFunction: DockerImageFunction;

  /**
   * The SNS topic for input data.
   */
  public inputTopic: ITopic;

  /**
   * The OpenSearch domain for data catalog.
   */
  public openSearchDomain: DCOpenSearchDomain;

  /**
   * The removal policy for resources created by this construct.
   */
  public removalPolicy: RemovalPolicy;

  /**
   * The IAM role for the Lambda functions.
   */
  public lambdaRole: IRole;

  /**
   * The security group for the Lambda functions.
   */
  public securityGroup?: ISecurityGroup;

  /**
   * The container for the STAC process.
   */
  private stacContainer: Container;

  /**
   * The container for the ingest process.
   */
  private ingestContainer: Container;

  /**
   * Constructs an instance of DCDataplane.
   *
   * @constructor
   * @param {Construct} scope - The scope/stack in which to define this construct.
   * @param {string} id - The id of this construct within the current scope.
   * @param {DCDataplaneProps} props - The properties of this construct.
   */
  constructor(scope: Construct, id: string, props: DCDataplaneProps) {
    super(scope, id);

    // Setup class from base properties
    this.setup(props);

    // Create OpenSearch domain
    this.openSearchDomain = new DCOpenSearchDomain(this, "DCOSDomain", {
      account: props.account,
      vpc: props.vpc
    });

    // Build the STAC lambda container image
    this.stacContainer = new Container(this, "DCStacContainer", {
      account: props.account,
      buildDockerImageCode: true,
      buildFromSource: this.config.BUILD_FROM_SOURCE,
      config: {
        CONTAINER_URI: this.config.CONTAINER_URI_STAC,
        CONTAINER_BUILD_PATH: this.config.CONTAINER_BUILD_PATH,
        CONTAINER_BUILD_TARGET: this.config.CONTAINER_BUILD_TARGET_STAC,
        CONTAINER_DOCKERFILE: this.config.CONTAINER_DOCKERFILE_STAC
      }
    });

    // Build the ingest lambda container image
    this.ingestContainer = new Container(this, "DCIngestContainer", {
      account: props.account,
      buildDockerImageCode: true,
      buildFromSource: this.config.BUILD_FROM_SOURCE,
      config: {
        CONTAINER_URI: this.config.CONTAINER_URI_INGEST,
        CONTAINER_BUILD_PATH: this.config.CONTAINER_BUILD_PATH,
        CONTAINER_BUILD_TARGET: this.config.CONTAINER_BUILD_TARGET_INGEST,
        CONTAINER_DOCKERFILE: this.config.CONTAINER_DOCKERFILE_INGEST
      }
    });

    // Define STAC Lambda function
    this.stacLambdaFunction = new DockerImageFunction(this, "StacFunction", {
      code: this.stacContainer.dockerImageCode,
      timeout: Duration.seconds(this.config.LAMBDA_TIMEOUT),
      functionName: this.config.LAMBDA_STAC_FUNCTION_NAME,
      environment: {
        OPENSEARCH_ENDPOINT: this.openSearchDomain.domain.domainEndpoint
      },
      memorySize: this.config.LAMBDA_MEMORY_SIZE,
      ephemeralStorageSize: Size.gibibytes(10),
      vpc: props.vpc.vpc,
      vpcSubnets: props.vpc.selectedSubnets,
      role: this.lambdaRole
    });

    // Add ingress rule from STAC function to OpenSearch
    this.openSearchDomain.securityGroup.addIngressRule(
      this.stacLambdaFunction.connections.securityGroups[0],
      Port.tcp(443),
      `from ${this.stacLambdaFunction.functionName}:443`
    );

    // Define ingest Lambda function
    this.ingestLambdaFunction = new DockerImageFunction(
      this,
      "IngestFunction",
      {
        code: this.ingestContainer.dockerImageCode,
        timeout: Duration.seconds(this.config.LAMBDA_TIMEOUT),
        functionName: this.config.LAMBDA_INGEST_FUNCTION_NAME,
        environment: {
          OPENSEARCH_ENDPOINT: this.openSearchDomain.domain.domainEndpoint
        },
        memorySize: this.config.LAMBDA_MEMORY_SIZE,
        ephemeralStorageSize: Size.gibibytes(10),
        vpc: props.vpc.vpc,
        vpcSubnets: props.vpc.selectedSubnets,
        role: this.lambdaRole
      }
    );

    // Add ingress rule from ingest function to OpenSearch
    this.openSearchDomain.securityGroup.addIngressRule(
      this.ingestLambdaFunction.connections.securityGroups[0],
      Port.tcp(443),
      `from ${this.ingestLambdaFunction.functionName}:443`
    );

    // Subscribe Lambda function to the SNS topic
    this.inputTopic.addSubscription(
      new LambdaSubscription(this.stacLambdaFunction)
    );
  }

  /**
   * Sets up the DCDataplane construct with the provided properties.
   */
  private setup(props: DCDataplaneProps): void {
    // Check if a custom configuration was provided
    if (props.config != undefined) {
      this.config = props.config;
    } else {
      this.config = new DCDataplaneConfig();
    }

    // Setup a removal policy
    this.removalPolicy = props.account.prodLike
      ? RemovalPolicy.RETAIN
      : RemovalPolicy.DESTROY;

    // Create an SNS topic for Data Catalog requests if needed
    if (props.inputTopic) {
      this.inputTopic = props.inputTopic;
    } else {
      this.inputTopic = new Topic(this, "DIOutputTopic", {
        topicName: this.config.SNS_INPUT_TOPIC_NAME
      });
    }

    // Create a lambda role
    this.lambdaRole = new DCLambdaRole(this, "DCLambdaRole", {
      account: props.account,
      roleName: "DCLambdaRole"
    }).role;
  }
}
