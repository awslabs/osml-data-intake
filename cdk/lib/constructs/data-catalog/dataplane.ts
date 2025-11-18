/*
 * Copyright 2024-2025 Amazon.com, Inc. or its affiliates.
 */

import { RemovalPolicy } from "aws-cdk-lib";
import {
  ISecurityGroup,
  IVpc,
  SecurityGroup,
  SubnetSelection
} from "aws-cdk-lib/aws-ec2";
import { IRole, Role } from "aws-cdk-lib/aws-iam";
import { ITopic, Topic } from "aws-cdk-lib/aws-sns";
import { NagSuppressions } from "cdk-nag";
import { Construct } from "constructs";

import { BaseConfig, ConfigType, OSMLAccount } from "../types";
import { Container } from "./container";
import { IngestFunction } from "./ingest-function";
import { IngestRole } from "./ingest-role";
import { OpenSearch } from "./opensearch";
import { StacApiGateway } from "./stac-api-gateway";
import { StacFunction } from "./stac-function";
import { StacRole } from "./stac-role";

/**
 * Represents the configuration for the DCDataplane Construct.
 */
export class DCDataplaneConfig extends BaseConfig {
  /**
   * The name of the service in abbreviation to use for the API.
   * @default "DC"
   */
  public API_SERVICE_NAME_ABBREVIATION: string;

  /**
   * Whether to build container resources from source.
   * @default "false"
   */
  public BUILD_FROM_SOURCE: boolean;

  /**
   * The build path for the Data Intake container.
   * @default "lib/osml-data-intake"
   */
  public CONTAINER_BUILD_PATH: string;

  /**
   * The build target for the Data Intake ingest Lambda container Dockerfile.
   * @default "ingest"
   */
  public INGEST_CONTAINER_BUILD_TARGET: string;

  /**
   * The relative Dockerfile to use to build the Data Intake ingest Lambda container.
   * @default "docker/Dockerfile.ingest"
   */
  public INGEST_CONTAINER_DOCKERFILE: string;

  /**
   * The container image to use for the Data Intake ingest Lambda.
   * @default "awsosml/osml-data-intake-ingest:latest"
   */
  public INGEST_CONTAINER_URI: string;

  /**
   * The memory size of the Lambda function (MB).
   * @default 4096
   */
  public LAMBDA_MEMORY_SIZE: number;

  /**
   * The security group ID to use for the Lambda container.
   * @default undefined
   */
  public LAMBDA_SECURITY_GROUP_ID?: string | undefined;

  /**
   * The name of the Lambda role.
   * @default "DCLambdaRole"
   */
  public LAMBDA_ROLE_NAME: string;

  /**
   * The storage size of the Lambda function (GB).
   * @default 10
   */
  public LAMBDA_STORAGE_SIZE: number;

  /**
   * The timeout of the Lambda function (Seconds).
   * @default 300
   */
  public LAMBDA_TIMEOUT: number;

  /**
   * The number of data nodes in the OpenSearch cluster.
   * @default 4
   */
  public OS_DATA_NODES: number;

  /**
   * The name to give a generated ingest SNS topic.
   * @default "osml-stac-ingest"
   */
  public SNS_INGEST_TOPIC_NAME: string;

  /**
   * The relative Dockerfile.stac to use to build the STAC API Lambda container.
   * @default "docker/Dockerfile.stac"
   */
  public STAC_CONTAINER_DOCKERFILE: string;

  /**
   * The build target for the Data Intake STAC API container Dockerfile.
   * @default "stac"
   */
  public STAC_CONTAINER_BUILD_TARGET: string;

  /**
   * The container image to use for the Data Intake STAC API lambda.
   * @default "awsosml/osml-data-intake-stac:latest"
   */
  public STAC_CONTAINER_URI: string;

  /**
   * The description of the STAC FastAPI application.
   * @default "A STAC FastAPI with an OpenSearch backend"
   */
  public STAC_FASTAPI_DESCRIPTION: string;

  /**
   * The root path for FASTAPI that is set by APIGateway.
   * @default "data-catalog"
   */
  public STAC_FASTAPI_ROOT_PATH: string;

  /**
   * The title of the STAC FastAPI application.
   * @default "stac-fastapi-opensearch"
   */
  public STAC_FASTAPI_TITLE: string;

  /**
   * The version of the STAC FastAPI application.
   * @default "2.4.1"
   */
  public STAC_FASTAPI_VERSION: string;

  /**
   * The environment of the application.
   * @default "local"
   */
  public STAC_ENVIRONMENT: string;

  /**
   * The port of the OpenSearch cluster.
   * @default "443"
   */
  public STAC_ES_PORT: string;

  /**
   * A boolean to use SSL.
   * @default "true"
   */
  public STAC_ES_USE_SSL: string;

  /**
   * Whether to verify traffic with SSL certs.
   * @default "true"
   */
  public STAC_ES_VERIFY_CERTS: string;

  /**
   * A boolean indicating whether to reload the application.
   * @default "true"
   */
  public STAC_RELOAD: string;

  /**
   * The web concurrency of the application.
   * @default "10"
   */
  public STAC_WEB_CONCURRENCY: string;

  /**
   * Creates an instance of DCDataplaneConfig.
   * @param config - The configuration object for DCDataplane.
   */
  constructor(config: ConfigType = {}) {
    super({
      API_SERVICE_NAME_ABBREVIATION: "DC",
      CONTAINER_BUILD_PATH: "../",
      INGEST_CONTAINER_BUILD_TARGET: "ingest",
      INGEST_CONTAINER_DOCKERFILE: "docker/Dockerfile.ingest",
      INGEST_CONTAINER_URI: "awsosml/osml-data-intake-ingest:latest",
      LAMBDA_MEMORY_SIZE: 4096,
      LAMBDA_STORAGE_SIZE: 10,
      LAMBDA_TIMEOUT: 300,
      OS_DATA_NODES: 4,
      SNS_INGEST_TOPIC_NAME: "osml-dc-ingest",
      STAC_CONTAINER_DOCKERFILE: "docker/Dockerfile.stac",
      STAC_CONTAINER_BUILD_TARGET: "stac",
      STAC_CONTAINER_URI: "awsosml/osml-data-intake-stac:latest",
      STAC_FASTAPI_DESCRIPTION: "A STAC FastAPI with an OpenSearch backend",
      STAC_FASTAPI_ROOT_PATH: "data-catalog",
      STAC_FASTAPI_TITLE: "stac-fastapi-opensearch",
      STAC_FASTAPI_VERSION: "2.4.1",
      STAC_ENVIRONMENT: "local",
      STAC_ES_PORT: "443",
      STAC_ES_USE_SSL: "true",
      STAC_ES_VERIFY_CERTS: "true",
      STAC_RELOAD: "true",
      STAC_WEB_CONCURRENCY: "10",
      ...config
    });
  }
}

/**
 * Interface representing the properties for the DCDataplane construct.
 */
export interface DCDataplaneProps {
  /**
   * The OSML deployment account.
   * @type {OSMLAccount}
   */
  account: OSMLAccount;

  /**
   * The VPC (Virtual Private Cloud) for the Dataplane.
   * @type {IVpc}
   */
  vpc: IVpc;

  /**
   * The selected subnets for the VPC.
   * @type {SubnetSelection}
   */
  selectedSubnets: SubnetSelection;

  /**
   * The topic to subscribe to for ingesting STAC items.
   */
  ingestTopic?: ITopic;

  /**
   * Custom configuration for the DCDataplane Construct (optional).
   * @type {DCDataplaneConfig | undefined}
   */
  config?: DCDataplaneConfig;
}

/**
 * Represents the Dataplane construct responsible for managing the data plane
 * of the data catalog application. It handles various AWS resources and configurations
 * required for the application's operation.
 *
 * This refactored version uses separate resource classes to improve maintainability
 * and reduce complexity.
 */
export class DCDataplane extends Construct {
  /** The configuration for the DCDataplane. */
  public readonly config: DCDataplaneConfig;
  /** The removal policy for resources created by this construct. */
  public readonly removalPolicy: RemovalPolicy;
  /** The security group associated with the resources created by this construct. */
  public readonly securityGroup: ISecurityGroup;
  /** IAM role used by the ingest Lambda function. */
  public readonly ingestLambdaRole: IRole;
  /** IAM role used by the STAC Lambda function. */
  public readonly stacLambdaRole: IRole;

  // Resource classes
  /** The SNS topic for ingesting STAC items. */
  public readonly ingestTopic: ITopic;
  /** The container for the ingest Lambda function. */
  public readonly ingestContainer: Container;
  /** The container for the STAC API Lambda function. */
  public readonly stacContainer: Container;
  /** The OpenSearch domain. */
  public readonly openSearchDomain: OpenSearch;
  /** The ingest Lambda function. */
  public readonly ingestFunction: IngestFunction;
  /** The STAC Lambda function. */
  public readonly stacFunction: StacFunction;
  /** The STAC API Gateway. */
  public readonly stacApiGateway: StacApiGateway;

  /**
   * Constructs an instance of DCDataplane.
   *
   * @param scope - The scope/stack in which to define this construct
   * @param id - The id of this construct within the current scope
   * @param props - The properties of this construct
   */
  constructor(scope: Construct, id: string, props: DCDataplaneProps) {
    super(scope, id);

    // Initialize configuration and basic properties
    this.config = this.initializeConfig(props);
    this.removalPolicy = this.initializeRemovalPolicy(props);
    this.securityGroup = this.initializeSecurityGroup(props);
    this.ingestLambdaRole = this.initializeIngestLambdaRole(props);
    this.stacLambdaRole = this.initializeStacLambdaRole(props);

    // Create resource classes
    this.ingestTopic = this.createIngestTopic(props);
    this.ingestContainer = this.createIngestContainer(props);
    this.stacContainer = this.createStacContainer(props);
    this.openSearchDomain = this.createOpenSearchDomain(props);
    this.ingestFunction = this.createIngestFunction(props);
    this.stacFunction = this.createStacFunction(props);
    this.stacApiGateway = this.createStacApiGateway(props);
  }

  /**
   * Initializes the configuration.
   *
   * @param props - The DCDataplane properties
   * @returns The initialized configuration
   */
  private initializeConfig(props: DCDataplaneProps): DCDataplaneConfig {
    if (props.config instanceof DCDataplaneConfig) {
      return props.config;
    }
    return new DCDataplaneConfig(
      (props.config as unknown as Partial<ConfigType>) ?? {}
    );
  }

  /**
   * Initializes the removal policy based on account type.
   *
   * @param props - The DCDataplane properties
   * @returns The removal policy
   */
  private initializeRemovalPolicy(props: DCDataplaneProps): RemovalPolicy {
    return props.account.prodLike
      ? RemovalPolicy.RETAIN
      : RemovalPolicy.DESTROY;
  }

  /**
   * Initializes the security group.
   *
   * @param props - The DCDataplane properties
   * @returns The security group
   */
  private initializeSecurityGroup(props: DCDataplaneProps): ISecurityGroup {
    if (this.config.LAMBDA_SECURITY_GROUP_ID) {
      return SecurityGroup.fromSecurityGroupId(
        this,
        "DCImportSecurityGroup",
        this.config.LAMBDA_SECURITY_GROUP_ID
      );
    }
    return new SecurityGroup(this, "DCOSSecurityGroup", {
      vpc: props.vpc
    });
  }

  /**
   * Initializes the ingest Lambda role.
   *
   * @param props - The DCDataplane properties
   * @returns The ingest Lambda role
   */
  private initializeIngestLambdaRole(props: DCDataplaneProps): IRole {
    if (
      this.config.LAMBDA_ROLE_NAME &&
      this.config.LAMBDA_ROLE_NAME !== undefined &&
      this.config.LAMBDA_ROLE_NAME !== ""
    ) {
      return Role.fromRoleName(
        this,
        "ImportedDCIngestLambdaRole",
        this.config.LAMBDA_ROLE_NAME,
        { mutable: false }
      );
    }
    return new IngestRole(this, "IngestRole", {
      account: props.account,
      roleName: "DCIngestLambdaRole"
    }).role;
  }

  /**
   * Initializes the STAC Lambda role.
   *
   * @param props - The DCDataplane properties
   * @returns The STAC Lambda role
   */
  private initializeStacLambdaRole(props: DCDataplaneProps): IRole {
    if (
      this.config.LAMBDA_ROLE_NAME &&
      this.config.LAMBDA_ROLE_NAME !== undefined &&
      this.config.LAMBDA_ROLE_NAME !== ""
    ) {
      // If a single role name is provided, use it for both (backward compatibility)
      return Role.fromRoleName(
        this,
        "ImportedDCStacLambdaRole",
        this.config.LAMBDA_ROLE_NAME,
        { mutable: false }
      );
    }
    return new StacRole(this, "StacRole", {
      account: props.account,
      roleName: "DCStacLambdaRole"
    }).role;
  }

  /**
   * Creates the ingest SNS topic.
   *
   * @param props - The DCDataplane properties
   * @returns The ingest SNS topic
   */
  private createIngestTopic(props: DCDataplaneProps): ITopic {
    if (props.ingestTopic) {
      return props.ingestTopic;
    }
    const topic = new Topic(this, "DCIngestTopic", {
      topicName: this.config.SNS_INGEST_TOPIC_NAME
    });

    // Add cdk-nag suppressions
    NagSuppressions.addResourceSuppressions(
      topic,
      [
        {
          id: "AwsSolutions-SNS2",
          reason:
            "SNS topic encryption is not required as the topic is used for internal service communication within the VPC. The topic is not exposed publicly and access is controlled via IAM policies."
        },
        {
          id: "AwsSolutions-SNS3",
          reason:
            "SSL requirement for publishers is not required as the topic is used for internal service communication within the VPC. Publishers are Lambda functions deployed in the same VPC with restricted network access."
        }
      ],
      true
    );

    return topic;
  }

  /**
   * Creates the ingest container.
   *
   * @param props - The DCDataplane properties
   * @returns The ingest container
   */
  private createIngestContainer(props: DCDataplaneProps): Container {
    return new Container(this, "DCIngestContainer", {
      account: props.account,
      buildDockerImageCode: true,
      buildFromSource: this.config.BUILD_FROM_SOURCE,
      config: {
        CONTAINER_URI: this.config.INGEST_CONTAINER_URI,
        CONTAINER_BUILD_PATH: this.config.CONTAINER_BUILD_PATH,
        CONTAINER_BUILD_TARGET: this.config.INGEST_CONTAINER_BUILD_TARGET,
        CONTAINER_DOCKERFILE: this.config.INGEST_CONTAINER_DOCKERFILE
      }
    });
  }

  /**
   * Creates the STAC container.
   *
   * @param props - The DCDataplane properties
   * @returns The STAC container
   */
  private createStacContainer(props: DCDataplaneProps): Container {
    return new Container(this, "DCSTACContainer", {
      account: props.account,
      buildDockerImageCode: true,
      buildFromSource: this.config.BUILD_FROM_SOURCE,
      config: {
        CONTAINER_URI: this.config.STAC_CONTAINER_URI,
        CONTAINER_BUILD_PATH: this.config.CONTAINER_BUILD_PATH,
        CONTAINER_BUILD_TARGET: this.config.STAC_CONTAINER_BUILD_TARGET,
        CONTAINER_DOCKERFILE: this.config.STAC_CONTAINER_DOCKERFILE
      }
    });
  }

  /**
   * Creates the OpenSearch domain.
   *
   * @param props - The DCDataplane properties
   * @returns The OpenSearch domain
   */
  private createOpenSearchDomain(props: DCDataplaneProps): OpenSearch {
    return new OpenSearch(this, "OpenSearchDomain", {
      account: props.account,
      vpc: props.vpc,
      selectedSubnets: props.selectedSubnets,
      securityGroup: this.securityGroup,
      config: this.config,
      removalPolicy: this.removalPolicy
    });
  }

  /**
   * Creates the ingest Lambda function.
   *
   * @param props - The DCDataplane properties
   * @returns The ingest Lambda function
   */
  private createIngestFunction(props: DCDataplaneProps): IngestFunction {
    return new IngestFunction(this, "IngestFunction", {
      account: props.account,
      vpc: props.vpc,
      selectedSubnets: props.selectedSubnets,
      lambdaRole: this.ingestLambdaRole,
      ingestContainer: this.ingestContainer,
      osDomain: this.openSearchDomain.domain,
      ingestTopic: this.ingestTopic,
      config: this.config
    });
  }

  /**
   * Creates the STAC Lambda function.
   *
   * @param props - The DCDataplane properties
   * @returns The STAC Lambda function
   */
  private createStacFunction(props: DCDataplaneProps): StacFunction {
    return new StacFunction(this, "StacFunction", {
      account: props.account,
      vpc: props.vpc,
      selectedSubnets: props.selectedSubnets,
      lambdaRole: this.stacLambdaRole,
      stacContainer: this.stacContainer,
      osDomain: this.openSearchDomain.domain,
      config: this.config
    });
  }

  /**
   * Creates the STAC API Gateway.
   *
   * @param props - The DCDataplane properties
   * @returns The STAC API Gateway
   */
  private createStacApiGateway(props: DCDataplaneProps): StacApiGateway {
    return new StacApiGateway(this, "StacApiGateway", {
      account: props.account,
      stacFunction: this.stacFunction.function,
      config: this.config,
      serviceNameAbbreviation: this.config.API_SERVICE_NAME_ABBREVIATION
    });
  }
}
