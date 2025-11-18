/*
 * Copyright 2023-2025 Amazon.com, Inc. or its affiliates.
 */

import { RemovalPolicy } from "aws-cdk-lib";
import {
  ISecurityGroup,
  IVpc,
  SecurityGroup,
  SubnetSelection
} from "aws-cdk-lib/aws-ec2";
import { IRole, Role } from "aws-cdk-lib/aws-iam";
import { Function } from "aws-cdk-lib/aws-lambda";
import { Bucket } from "aws-cdk-lib/aws-s3";
import { ITopic, Topic } from "aws-cdk-lib/aws-sns";
import { Construct } from "constructs";

import { Container } from "../data-catalog/container";
import { BaseConfig, ConfigType, OSMLAccount } from "../types";
import { LambdaFunction } from "./lambda-function";
import { DILambdaRole } from "./lambda-role";
import { MetadataStorage } from "./metadata-storage";

/**
 * Configuration class for DIDataplane Construct.
 */
export class DIDataplaneConfig extends BaseConfig {
  /**
   * Whether to build container resources from source.
   * @default "false"
   */
  public BUILD_FROM_SOURCE: boolean;

  /**
   * The build path for the Data Intake.
   * @default "../"
   */
  public CONTAINER_BUILD_PATH: string;

  /**
   * The build target for the Data Intake.
   * @default "intake"
   */
  public CONTAINER_BUILD_TARGET: string;

  /**
   * The relative Dockerfile to use to build the container.
   * @default "docker/Dockerfile.intake"
   */
  public CONTAINER_DOCKERFILE: string;

  /**
   * The container image to use for the Data Intake lambda.
   * @default "awsosml/osml-data-intake-intake:latest"
   */
  public CONTAINER_URI: string;

  /**
   * The name of the Lambda for the Data Intake.
   * @default "DILambda"
   */
  public LAMBDA_FUNCTION_NAME: string;

  /**
   * The memory in MB to give the lambda runtime.
   * @default 1024
   */
  public LAMBDA_MEMORY_SIZE: number;

  /**
   * The name of the DI Lambda execution role.
   * @default undefined
   */
  public LAMBDA_ROLE_NAME?: string | undefined;

  /**
   * The security group ID to use for the Lambda container.
   * @default undefined
   */
  public LAMBDA_SECURITY_GROUP_ID?: string | undefined;

  /**
   * The size of the storage to assign lambda runtime in GB.
   * @default 10
   */
  public LAMBDA_STORAGE_SIZE: number;

  /**
   * The timeout, in seconds, for the Lambda function.
   * @default 900
   */
  public LAMBDA_TIMEOUT: number;

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
   * The name to give the output SNS topic.
   * @default "osml-stac-ingest"
   */
  public SNS_STAC_TOPIC_NAME: string;

  /**
   * Constructor for DIDataplane Construct.
   * @param config - The configuration object for DIDataplane.
   */
  constructor(config: ConfigType = {}) {
    super({
      BUILD_FROM_SOURCE: false,
      CONTAINER_BUILD_PATH: "../",
      CONTAINER_BUILD_TARGET: "intake",
      CONTAINER_DOCKERFILE: "docker/Dockerfile.intake",
      CONTAINER_URI: "awsosml/osml-data-intake-intake:latest",
      LAMBDA_FUNCTION_NAME: "DILambda",
      LAMBDA_MEMORY_SIZE: 1024,
      LAMBDA_STORAGE_SIZE: 10,
      LAMBDA_TIMEOUT: 900,
      S3_OUTPUT_BUCKET_NAME: "di-output-bucket",
      SNS_INPUT_TOPIC_NAME: "osml-data-intake",
      SNS_STAC_TOPIC_NAME: "osml-di-ingest",
      ...config
    });
  }
}

/**
 * Interface representing properties for configuring the DIDataplane Construct.
 */
export interface DIDataplaneProps {
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
   * The input topic to receive Data Intake requests (optional).
   * @type {Topic | undefined}
   */
  inputTopic?: ITopic;

  /**
   * The output topic to send generated STAC items (optional).
   * @type {Topic | undefined}
   */
  stacTopic?: ITopic;

  /**
   * Custom configuration for the DIDataplane Construct (optional).
   * @type {DIDataplaneConfig | undefined}
   */
  config?: DIDataplaneConfig;
}

/**
 * Represents the DIDataplane construct responsible for managing the data plane
 * of the data intake application. It handles various AWS resources and configurations
 * required for the application's operation.
 *
 * This refactored version uses separate resource classes to improve maintainability
 * and reduce complexity.
 */
export class DIDataplane extends Construct {
  /** The configuration for the DIDataplane. */
  public readonly config: DIDataplaneConfig;
  /** The removal policy for resources created by this construct. */
  public readonly removalPolicy: RemovalPolicy;
  /** The security group for the Lambda function (optional). */
  public readonly securityGroup?: ISecurityGroup;
  /** The IAM role for the Lambda function. */
  public readonly lambdaRole: IRole;

  // Resource classes
  /** The SNS topic for input data. */
  public readonly inputTopic: ITopic;
  /** The SNS topic for STAC item outputs. */
  public readonly stacTopic: ITopic;
  /** The metadata storage resource. */
  public readonly storage: MetadataStorage;
  /** The container for the data intake process. */
  public readonly container: Container;
  /** The Lambda function resources. */
  public readonly lambdaFunctionResource: LambdaFunction;

  // Convenience properties for backward compatibility
  /** The Lambda function for data intake. */
  public get lambdaFunction(): Function {
    return this.lambdaFunctionResource.lambdaFunction;
  }

  /** The S3 bucket for output data. */
  public get outputBucket(): Bucket {
    return this.storage.outputBucket;
  }

  /**
   * Constructs an instance of DIDataplane.
   *
   * @param scope - The scope/stack in which to define this construct
   * @param id - The id of this construct within the current scope
   * @param props - The properties of this construct
   */
  constructor(scope: Construct, id: string, props: DIDataplaneProps) {
    super(scope, id);

    // Initialize configuration and basic properties
    this.config = this.initializeConfig(props);
    this.removalPolicy = this.initializeRemovalPolicy(props);
    this.securityGroup = this.initializeSecurityGroup();
    this.lambdaRole = this.initializeLambdaRole(props);

    // Create resource classes
    this.inputTopic = this.createInputTopic(props);
    this.stacTopic = this.createStacTopic(props);
    this.storage = this.createStorage(props);
    this.container = this.createContainer(props);
    this.lambdaFunctionResource = this.createLambdaFunction(props);
  }

  /**
   * Initializes the configuration.
   *
   * @param props - The DIDataplane properties
   * @returns The initialized configuration
   */
  private initializeConfig(props: DIDataplaneProps): DIDataplaneConfig {
    if (props.config instanceof DIDataplaneConfig) {
      return props.config;
    }
    return new DIDataplaneConfig(
      (props.config as unknown as Partial<ConfigType>) ?? {}
    );
  }

  /**
   * Initializes the removal policy based on account type.
   *
   * @param props - The DIDataplane properties
   * @returns The removal policy
   */
  private initializeRemovalPolicy(props: DIDataplaneProps): RemovalPolicy {
    return props.account.prodLike
      ? RemovalPolicy.RETAIN
      : RemovalPolicy.DESTROY;
  }

  /**
   * Initializes the security group if specified.
   *
   * @returns The security group or undefined
   */
  private initializeSecurityGroup(): ISecurityGroup | undefined {
    if (this.config.LAMBDA_SECURITY_GROUP_ID) {
      return SecurityGroup.fromSecurityGroupId(
        this,
        "DIImportSecurityGroup",
        this.config.LAMBDA_SECURITY_GROUP_ID
      );
    }
    return undefined;
  }

  /**
   * Initializes the Lambda role.
   *
   * @param props - The DIDataplane properties
   * @returns The Lambda role
   */
  private initializeLambdaRole(props: DIDataplaneProps): IRole {
    if (
      this.config.LAMBDA_ROLE_NAME &&
      this.config.LAMBDA_ROLE_NAME !== undefined &&
      this.config.LAMBDA_ROLE_NAME !== ""
    ) {
      return Role.fromRoleName(
        this,
        "ImportedDILambdaRole",
        this.config.LAMBDA_ROLE_NAME,
        { mutable: false }
      );
    }
    return new DILambdaRole(this, "DILambdaRole", {
      account: props.account,
      roleName: "DILambdaRole"
    }).role;
  }

  /**
   * Creates the input SNS topic.
   *
   * @param props - The DIDataplane properties
   * @returns The input SNS topic
   */
  private createInputTopic(props: DIDataplaneProps): ITopic {
    if (props.inputTopic) {
      return props.inputTopic;
    }
    return new Topic(this, "DIInputTopic", {
      topicName: this.config.SNS_INPUT_TOPIC_NAME
    });
  }

  /**
   * Creates the STAC SNS topic.
   *
   * @param props - The DIDataplane properties
   * @returns The STAC SNS topic
   */
  private createStacTopic(props: DIDataplaneProps): ITopic {
    if (props.stacTopic) {
      return props.stacTopic;
    }
    return new Topic(this, "DIOutputTopic", {
      topicName: this.config.SNS_STAC_TOPIC_NAME
    });
  }

  /**
   * Creates the metadata storage resource.
   *
   * @param props - The DIDataplane properties
   * @returns The metadata storage resource
   */
  private createStorage(props: DIDataplaneProps): MetadataStorage {
    return new MetadataStorage(this, "MetadataStorage", {
      account: props.account,
      config: this.config,
      removalPolicy: this.removalPolicy
    });
  }

  /**
   * Creates the container resource.
   *
   * @param props - The DIDataplane properties
   * @returns The container resource
   */
  private createContainer(props: DIDataplaneProps): Container {
    return new Container(this, "DIContainer", {
      account: props.account,
      buildDockerImageCode: true,
      buildFromSource: this.config.BUILD_FROM_SOURCE,
      config: {
        CONTAINER_URI: this.config.CONTAINER_URI,
        CONTAINER_BUILD_PATH: this.config.CONTAINER_BUILD_PATH,
        CONTAINER_BUILD_TARGET: this.config.CONTAINER_BUILD_TARGET,
        CONTAINER_DOCKERFILE: this.config.CONTAINER_DOCKERFILE
      }
    });
  }

  /**
   * Creates the Lambda function resources.
   *
   * @param props - The DIDataplane properties
   * @returns The Lambda function resources
   */
  private createLambdaFunction(props: DIDataplaneProps): LambdaFunction {
    return new LambdaFunction(this, "LambdaFunction", {
      account: props.account,
      vpc: props.vpc,
      selectedSubnets: props.selectedSubnets,
      lambdaRole: this.lambdaRole,
      container: this.container,
      outputBucket: this.storage.outputBucket,
      stacTopic: this.stacTopic,
      inputTopic: this.inputTopic,
      securityGroup: this.securityGroup,
      config: this.config
    });
  }
}
