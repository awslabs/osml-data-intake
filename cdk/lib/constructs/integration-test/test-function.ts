/*
 * Copyright 2024-2025 Amazon.com, Inc. or its affiliates.
 */

import { Duration, RemovalPolicy, Size } from "aws-cdk-lib";
import { IVpc, SubnetSelection } from "aws-cdk-lib/aws-ec2";
import { IRole, Role } from "aws-cdk-lib/aws-iam";
import {
  DockerImageFunction,
  Function,
  IFunction,
  LoggingFormat
} from "aws-cdk-lib/aws-lambda";
import { CfnLogGroup } from "aws-cdk-lib/aws-logs";
import { Bucket } from "aws-cdk-lib/aws-s3";
import { ITopic } from "aws-cdk-lib/aws-sns";
import { Construct } from "constructs";

import { Container, ContainerConfig } from "../data-catalog/container";
import { BaseConfig, ConfigType, OSMLAccount } from "../types";
import { IntegrationTestRole } from "./test-role";

/**
 * Represents the configuration for the Integration Test Construct.
 */
export class IntegrationTestConfig extends BaseConfig {
  /**
   * Whether to build container resources from source.
   * @default false
   */
  public BUILD_FROM_SOURCE: boolean;

  /**
   * The build path for the Integration Test container.
   * @default "../"
   */
  public CONTAINER_BUILD_PATH: string;

  /**
   * The build target for the Integration Test container Dockerfile.
   * @default "integration-test"
   */
  public INTEGRATION_TEST_CONTAINER_BUILD_TARGET: string;

  /**
   * The relative Dockerfile to use to build the Integration Test container.
   * @default "docker/Dockerfile.integration-test"
   */
  public INTEGRATION_TEST_CONTAINER_DOCKERFILE: string;

  /**
   * The container image to use for the Integration Test lambda.
   * @default "awsosml/osml-data-intake-integration-test:latest"
   */
  public INTEGRATION_TEST_CONTAINER_URI: string;

  /**
   * The name of the Integration Test Lambda role to import.
   * @default undefined
   */
  public INTEGRATION_TEST_LAMBDA_ROLE_NAME: string | undefined;

  /**
   * The STAC API root path.
   * @default "data-catalog"
   */
  public STAC_FASTAPI_ROOT_PATH: string;

  /**
   * The collection ID to use for integration tests.
   * @default "OSML"
   */
  public COLLECTION_ID: string;

  /**
   * Maximum wait time in seconds for item processing.
   * @default "60"
   */
  public MAX_WAIT_SECONDS: string;

  /**
   * Wait interval in seconds between polling attempts.
   * @default "5"
   */
  public WAIT_INTERVAL_SECONDS: string;

  /**
   * Creates an instance of IntegrationTestConfig.
   * @param config - The configuration object for Integration Test.
   */
  constructor(config: ConfigType = {}) {
    super({
      BUILD_FROM_SOURCE: false,
      CONTAINER_BUILD_PATH: "../",
      INTEGRATION_TEST_CONTAINER_BUILD_TARGET: "integration-test",
      INTEGRATION_TEST_CONTAINER_DOCKERFILE:
        "docker/Dockerfile.integration-test",
      INTEGRATION_TEST_CONTAINER_URI:
        "awsosml/osml-data-intake-integration-test:latest",
      COLLECTION_ID: "OSML",
      STAC_FASTAPI_ROOT_PATH: "data-catalog",
      MAX_WAIT_SECONDS: "60",
      WAIT_INTERVAL_SECONDS: "5",
      ...config
    });
  }
}

/**
 * Properties for creating the integration test Lambda function.
 */
export interface IntegrationTestFunctionProps {
  /** The OSML account configuration. */
  readonly account: OSMLAccount;
  /** The VPC configuration. */
  readonly vpc: IVpc;
  /** The selected subnets for the VPC. */
  readonly selectedSubnets: SubnetSelection;
  /** The input S3 bucket for test images. */
  readonly inputBucket: Bucket;
  /** The input SNS topic. */
  readonly inputTopic: ITopic;
  /** The STAC Lambda function. */
  readonly stacFunction: IFunction;
  /** The security group for the Lambda function (optional). */
  readonly securityGroup?: import("aws-cdk-lib/aws-ec2").ISecurityGroup;
  /** The integration test configuration. */
  readonly config: IntegrationTestConfig;
  /** The removal policy for resources. */
  readonly removalPolicy: RemovalPolicy;
}

/**
 * Construct that manages the integration test Lambda function for the Data Catalog.
 *
 * This construct encapsulates the creation and configuration of the Lambda
 * function for integration testing.
 */
export class IntegrationTestFunction extends Construct {
  /** The Lambda function for integration testing. */
  public readonly function: Function;
  /** The IAM role for the Lambda function. */
  public readonly role: IRole;
  /** The container for the Lambda function. */
  public readonly container: Container;

  /**
   * Creates a new IntegrationTestFunction construct.
   *
   * @param scope - The scope/stack in which to define this construct
   * @param id - The id of this construct within the current scope
   * @param props - The properties for configuring this construct
   */
  constructor(
    scope: Construct,
    id: string,
    props: IntegrationTestFunctionProps
  ) {
    super(scope, id);

    // Initialize the Lambda role
    this.role = this.initializeRole(props);

    // Create the integration test container
    this.container = this.createContainer(props);

    // Create the integration test Lambda function
    this.function = new DockerImageFunction(
      this,
      "DataCatalogIntegrationTestFunction",
      {
        functionName: "data-catalog-integration-test",
        code: this.container.dockerImageCode,
        role: this.role,
        vpc: props.vpc,
        vpcSubnets: props.selectedSubnets,
        timeout: Duration.seconds(600), // 10 minutes for integration test
        ephemeralStorageSize: Size.gibibytes(1),
        memorySize: 512,
        environment: {
          INPUT_BUCKET: props.inputBucket.bucketName,
          INPUT_TOPIC_ARN: props.inputTopic.topicArn,
          STAC_FUNCTION_NAME: props.stacFunction.functionName,
          STAC_ROOT_PATH: props.config.STAC_FASTAPI_ROOT_PATH,
          COLLECTION_ID: props.config.COLLECTION_ID,
          MAX_WAIT_SECONDS: props.config.MAX_WAIT_SECONDS,
          WAIT_INTERVAL_SECONDS: props.config.WAIT_INTERVAL_SECONDS
        },
        securityGroups: props.securityGroup ? [props.securityGroup] : [],
        loggingFormat: LoggingFormat.JSON
      }
    );
    this.function.node.addDependency(this.container);

    // Set removal policy on the automatically created log group
    if (this.function.logGroup) {
      const logGroupResource = this.function.logGroup.node
        .defaultChild as CfnLogGroup;
      if (logGroupResource) {
        logGroupResource.applyRemovalPolicy(props.removalPolicy);
      }
    }
  }

  /**
   * Initializes the integration test Lambda role.
   *
   * @param props - The IntegrationTestFunction properties
   * @returns The integration test Lambda role
   */
  private initializeRole(props: IntegrationTestFunctionProps): IRole {
    if (
      props.config.INTEGRATION_TEST_LAMBDA_ROLE_NAME &&
      props.config.INTEGRATION_TEST_LAMBDA_ROLE_NAME !== undefined &&
      props.config.INTEGRATION_TEST_LAMBDA_ROLE_NAME !== ""
    ) {
      return Role.fromRoleName(
        this,
        "ImportedIntegrationTestRole",
        props.config.INTEGRATION_TEST_LAMBDA_ROLE_NAME,
        { mutable: false }
      );
    }
    return new IntegrationTestRole(this, "IntegrationTestRole", {
      account: props.account,
      roleName: "IntegrationTestLambdaRole",
      stacFunction: props.stacFunction,
      inputBucketArn: props.inputBucket.bucketArn
    }).role;
  }

  /**
   * Creates the integration test container.
   *
   * @param props - The IntegrationTestFunction properties
   * @returns The integration test container
   */
  private createContainer(props: IntegrationTestFunctionProps): Container {
    return new Container(this, "IntegrationTestContainer", {
      account: props.account,
      buildDockerImageCode: true,
      buildFromSource: props.config.BUILD_FROM_SOURCE,
      config: new ContainerConfig({
        CONTAINER_URI: props.config.INTEGRATION_TEST_CONTAINER_URI,
        CONTAINER_BUILD_PATH: props.config.CONTAINER_BUILD_PATH,
        CONTAINER_BUILD_TARGET:
          props.config.INTEGRATION_TEST_CONTAINER_BUILD_TARGET,
        CONTAINER_DOCKERFILE: props.config.INTEGRATION_TEST_CONTAINER_DOCKERFILE
      })
    });
  }
}
