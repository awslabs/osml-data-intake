/*
 * Copyright 2024-2026 Amazon.com, Inc. or its affiliates.
 */

import { RemovalPolicy } from "aws-cdk-lib";
import {
  ISecurityGroup,
  IVpc,
  SecurityGroup,
  SubnetSelection
} from "aws-cdk-lib/aws-ec2";
import { ITopic, Topic } from "aws-cdk-lib/aws-sns";
import { NagSuppressions } from "cdk-nag";
import { Construct } from "constructs";

import { BaseConfig, ConfigType, OSMLAccount } from "../types";
import { IngestFunction } from "./ingest-function";
import { IntakeFunction } from "./intake-function";
import { MetadataStorage } from "./metadata-storage";
import { OpenSearch } from "./opensearch";
import { StacFunction } from "./stac-function";

/**
 * Represents the configuration for the Dataplane Construct.
 */
export class DataplaneConfig extends BaseConfig {
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

  // Data Intake Configuration
  /**
   * The build target for the Data Intake container.
   * @default "intake"
   */
  public INTAKE_CONTAINER_BUILD_TARGET: string;

  /**
   * The relative Dockerfile to use to build the Data Intake container.
   * @default "docker/Dockerfile.intake"
   */
  public INTAKE_CONTAINER_DOCKERFILE: string;

  /**
   * The container image to use for the Data Intake lambda.
   * @default "awsosml/osml-data-intake-intake:latest"
   */
  public INTAKE_CONTAINER_URI: string;

  /**
   * The memory in MB to give the intake lambda runtime.
   * @default 1024
   */
  public INTAKE_LAMBDA_MEMORY_SIZE: number;

  /**
   * The name of the Intake Lambda execution role to import.
   * @default undefined
   */
  public INTAKE_LAMBDA_ROLE_NAME: string | undefined;

  /**
   * The size of the storage to assign intake lambda runtime in GB.
   * @default 10
   */
  public INTAKE_LAMBDA_STORAGE_SIZE: number;

  /**
   * The timeout, in seconds, for the Intake Lambda function.
   * @default 900
   */
  public INTAKE_LAMBDA_TIMEOUT: number;

  /**
   * Whether to deconstruct GeoJSON FeatureCollections into multiple items.
   * @default "false"
   */
  public DECONSTRUCT_FEATURE_COLLECTIONS: string;

  /**
   * The name to give the output bucket.
   * @default "di-output-bucket"
   */
  public S3_OUTPUT_BUCKET_NAME: string;

  /**
   * The name to give the input SNS topic.
   * @default "osml-data-intake"
   */
  public SNS_INPUT_TOPIC_NAME: string;

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
   * The memory size of the Ingest Lambda function (MB).
   * @default 4096
   */
  public INGEST_LAMBDA_MEMORY_SIZE: number;

  /**
   * The security group ID to use for the Lambda container.
   * @default undefined
   */
  public LAMBDA_SECURITY_GROUP_ID?: string | undefined;

  /**
   * The name of the Ingest Lambda role to import.
   * @default undefined
   */
  public INGEST_LAMBDA_ROLE_NAME: string | undefined;

  /**
   * The storage size of the Ingest Lambda function (GB).
   * @default 10
   */
  public INGEST_LAMBDA_STORAGE_SIZE: number;

  /**
   * The timeout of the Ingest Lambda function (Seconds).
   * @default 300
   */
  public INGEST_LAMBDA_TIMEOUT: number;

  /**
   * The memory size of the STAC Lambda function (MB).
   * @default 4096
   */
  public STAC_LAMBDA_MEMORY_SIZE: number;

  /**
   * The name of the STAC Lambda role to import.
   * @default undefined
   */
  public STAC_LAMBDA_ROLE_NAME: string | undefined;

  /**
   * The storage size of the STAC Lambda function (GB).
   * @default 10
   */
  public STAC_LAMBDA_STORAGE_SIZE: number;

  /**
   * The timeout of the STAC Lambda function (Seconds).
   * @default 300
   */
  public STAC_LAMBDA_TIMEOUT: number;

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
   * The root path for FASTAPI.
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
   * Creates an instance of DataplaneConfig.
   * @param config - The configuration object for Dataplane.
   */
  constructor(config: ConfigType = {}) {
    super({
      API_SERVICE_NAME_ABBREVIATION: "DataCatalog",
      CONTAINER_BUILD_PATH: "../",
      INGEST_CONTAINER_BUILD_TARGET: "ingest",
      INGEST_CONTAINER_DOCKERFILE: "docker/Dockerfile.ingest",
      INGEST_CONTAINER_URI: "awsosml/osml-data-intake-ingest:latest",
      INTAKE_CONTAINER_BUILD_TARGET: "intake",
      INTAKE_CONTAINER_DOCKERFILE: "docker/Dockerfile.intake",
      INTAKE_CONTAINER_URI: "awsosml/osml-data-intake-intake:latest",
      INTAKE_LAMBDA_MEMORY_SIZE: 1024,
      INTAKE_LAMBDA_STORAGE_SIZE: 10,
      INTAKE_LAMBDA_TIMEOUT: 900,
      DECONSTRUCT_FEATURE_COLLECTIONS: "false",
      INGEST_LAMBDA_MEMORY_SIZE: 4096,
      INGEST_LAMBDA_STORAGE_SIZE: 10,
      INGEST_LAMBDA_TIMEOUT: 300,
      STAC_LAMBDA_MEMORY_SIZE: 4096,
      STAC_LAMBDA_STORAGE_SIZE: 10,
      STAC_LAMBDA_TIMEOUT: 300,
      OS_DATA_NODES: 4,
      S3_OUTPUT_BUCKET_NAME: "metadata-storage",
      SNS_INPUT_TOPIC_NAME: "data-catalog-intake",
      SNS_INGEST_TOPIC_NAME: "data-catalog-ingest",
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
 * Interface representing the properties for the Dataplane construct.
 */
export interface DataplaneProps {
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
   * Custom configuration for the Dataplane Construct (optional).
   * @type {DataplaneConfig | undefined}
   */
  config?: DataplaneConfig;
}

/**
 * Represents the Dataplane construct responsible for managing the data plane
 * of the data catalog application. It handles various AWS resources and configurations
 * required for the application's operation.
 *
 * This refactored version uses separate resource classes to improve maintainability
 * and reduce complexity.
 */
export class Dataplane extends Construct {
  /** The configuration for the Dataplane. */
  public readonly config: DataplaneConfig;
  /** The removal policy for resources created by this construct. */
  public readonly removalPolicy: RemovalPolicy;
  /** The security group associated with the resources created by this construct. */
  public readonly securityGroup: ISecurityGroup;

  // Resource classes
  /** The SNS topic for input data intake requests. */
  public readonly inputTopic: ITopic;
  /** The SNS topic for ingesting STAC items (output from intake, input to ingest). */
  public readonly ingestTopic: ITopic;
  /** The metadata storage resource (S3 bucket). */
  public readonly metadataStorage: MetadataStorage;
  /** The OpenSearch domain. */
  public readonly openSearchDomain: OpenSearch;
  /** The intake Lambda function. */
  public readonly intakeFunction: IntakeFunction;
  /** The ingest Lambda function. */
  public readonly ingestFunction: IngestFunction;
  /** The STAC Lambda function. */
  public readonly stacFunction: StacFunction;

  /**
   * Constructs an instance of Dataplane.
   *
   * @param scope - The scope/stack in which to define this construct
   * @param id - The id of this construct within the current scope
   * @param props - The properties of this construct
   */
  constructor(scope: Construct, id: string, props: DataplaneProps) {
    super(scope, id);

    // Initialize configuration and basic properties
    this.config = this.initializeConfig(props);
    this.removalPolicy = this.initializeRemovalPolicy(props);
    this.securityGroup = this.initializeSecurityGroup(props);

    // Create resource classes
    this.inputTopic = this.createInputTopic();
    this.ingestTopic = this.createIngestTopic(props);
    this.metadataStorage = this.createMetadataStorage(props);
    this.openSearchDomain = this.createOpenSearchDomain(props);
    this.stacFunction = this.createStacFunction(props);
    this.intakeFunction = this.createIntakeFunction(props);
    this.ingestFunction = this.createIngestFunction(props);
  }

  /**
   * Initializes the configuration.
   *
   * @param props - The Dataplane properties
   * @returns The initialized configuration
   */
  private initializeConfig(props: DataplaneProps): DataplaneConfig {
    if (props.config instanceof DataplaneConfig) {
      return props.config;
    }
    return new DataplaneConfig(
      (props.config as unknown as Partial<ConfigType>) ?? {}
    );
  }

  /**
   * Initializes the removal policy based on account type.
   *
   * @param props - The Dataplane properties
   * @returns The removal policy
   */
  private initializeRemovalPolicy(props: DataplaneProps): RemovalPolicy {
    return props.account.prodLike || false
      ? RemovalPolicy.RETAIN
      : RemovalPolicy.DESTROY;
  }

  /**
   * Initializes the security group.
   *
   * @param props - The Dataplane properties
   * @returns The security group
   */
  private initializeSecurityGroup(props: DataplaneProps): ISecurityGroup {
    if (this.config.LAMBDA_SECURITY_GROUP_ID) {
      return SecurityGroup.fromSecurityGroupId(
        this,
        "DCImportSecurityGroup",
        this.config.LAMBDA_SECURITY_GROUP_ID
      );
    }
    return new SecurityGroup(this, "DCSecurityGroup", {
      vpc: props.vpc
    });
  }

  /**
   * Creates the input SNS topic for data intake requests.
   *
   * @returns The input SNS topic
   */
  private createInputTopic(): ITopic {
    const topic = new Topic(this, "InputTopic", {
      topicName: this.config.SNS_INPUT_TOPIC_NAME
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
   * Creates the ingest SNS topic (output from intake, input to ingest).
   *
   * @param props - The Dataplane properties
   * @returns The ingest SNS topic
   */
  private createIngestTopic(props: DataplaneProps): ITopic {
    if (props.ingestTopic) {
      return props.ingestTopic;
    }
    const topic = new Topic(this, "IngestTopic", {
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
   * Creates the metadata storage resource.
   *
   * @param props - The Dataplane properties
   * @returns The metadata storage resource
   */
  private createMetadataStorage(props: DataplaneProps): MetadataStorage {
    return new MetadataStorage(this, "MetadataStorage", {
      account: props.account,
      config: this.config,
      removalPolicy: this.removalPolicy
    });
  }

  /**
   * Creates the OpenSearch domain.
   *
   * @param props - The Dataplane properties
   * @returns The OpenSearch domain
   */
  private createOpenSearchDomain(props: DataplaneProps): OpenSearch {
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
   * Creates the intake Lambda function.
   *
   * @param props - The Dataplane properties
   * @returns The intake Lambda function
   */
  private createIntakeFunction(props: DataplaneProps): IntakeFunction {
    return new IntakeFunction(this, "IntakeFunction", {
      account: props.account,
      vpc: props.vpc,
      selectedSubnets: props.selectedSubnets,
      outputBucket: this.metadataStorage.outputBucket,
      stacTopic: this.ingestTopic, // Intake outputs to ingest topic
      inputTopic: this.inputTopic,
      securityGroup: this.securityGroup,
      config: this.config,
      removalPolicy: this.removalPolicy
    });
  }

  /**
   * Creates the ingest Lambda function.
   *
   * @param props - The Dataplane properties
   * @returns The ingest Lambda function
   */
  private createIngestFunction(props: DataplaneProps): IngestFunction {
    return new IngestFunction(this, "IngestFunction", {
      account: props.account,
      vpc: props.vpc,
      selectedSubnets: props.selectedSubnets,
      osDomain: this.openSearchDomain.domain,
      ingestTopic: this.ingestTopic,
      securityGroup: this.securityGroup,
      config: this.config,
      removalPolicy: this.removalPolicy
    });
  }

  /**
   * Creates the STAC Lambda function.
   *
   * @param props - The Dataplane properties
   * @returns The STAC Lambda function
   */
  private createStacFunction(props: DataplaneProps): StacFunction {
    return new StacFunction(this, "StacFunction", {
      account: props.account,
      vpc: props.vpc,
      selectedSubnets: props.selectedSubnets,
      osDomain: this.openSearchDomain.domain,
      securityGroup: this.securityGroup,
      config: this.config,
      removalPolicy: this.removalPolicy
    });
  }
}
