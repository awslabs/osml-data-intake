/*
 * Copyright 2024-2025 Amazon.com, Inc. or its affiliates.
 */

import { Duration, RemovalPolicy, Size } from "aws-cdk-lib";
import { IVpc, SubnetSelection } from "aws-cdk-lib/aws-ec2";
import { IRole, Role } from "aws-cdk-lib/aws-iam";
import {
  DockerImageFunction,
  Function,
  LoggingFormat
} from "aws-cdk-lib/aws-lambda";
import { CfnLogGroup } from "aws-cdk-lib/aws-logs";
import { Bucket } from "aws-cdk-lib/aws-s3";
import { ITopic } from "aws-cdk-lib/aws-sns";
import { LambdaSubscription } from "aws-cdk-lib/aws-sns-subscriptions";
import { Construct } from "constructs";

import { OSMLAccount } from "../types";
import { Container, ContainerConfig } from "./container";
import { DataplaneConfig } from "./dataplane";
import { IntakeRole } from "./intake-role";

/**
 * Properties for creating the intake Lambda function.
 */
export interface IntakeFunctionProps {
  /** The OSML account configuration. */
  readonly account: OSMLAccount;
  /** The VPC configuration. */
  readonly vpc: IVpc;
  /** The selected subnets for the VPC. */
  readonly selectedSubnets: SubnetSelection;
  /** The S3 output bucket. */
  readonly outputBucket: Bucket;
  /** The STAC SNS topic. */
  readonly stacTopic: ITopic;
  /** The input SNS topic. */
  readonly inputTopic: ITopic;
  /** The security group for the Lambda function (optional). */
  readonly securityGroup?: import("aws-cdk-lib/aws-ec2").ISecurityGroup;
  /** The DC dataplane configuration. */
  readonly config: DataplaneConfig;
  /** The removal policy for resources. */
  readonly removalPolicy: RemovalPolicy;
}

/**
 * Construct that manages the intake Lambda function for the Data Catalog.
 *
 * This construct encapsulates the creation and configuration of the Lambda
 * function for data intake.
 */
export class IntakeFunction extends Construct {
  /** The Lambda function for data intake. */
  public readonly function: Function;
  /** The IAM role for the Lambda function. */
  public readonly role: IRole;
  /** The container for the Lambda function. */
  public readonly container: Container;

  /**
   * Creates a new IntakeFunction construct.
   *
   * @param scope - The scope/stack in which to define this construct
   * @param id - The id of this construct within the current scope
   * @param props - The properties for configuring this construct
   */
  constructor(scope: Construct, id: string, props: IntakeFunctionProps) {
    super(scope, id);

    // Initialize the Lambda role
    this.role = this.initializeRole(props);

    // Create the intake container
    this.container = this.createContainer(props);

    // Create the intake Lambda function
    this.function = new DockerImageFunction(this, "DataCatalogIntakeFunction", {
      functionName: "data-catalog-intake",
      code: this.container.dockerImageCode,
      role: this.role,
      vpc: props.vpc,
      vpcSubnets: props.selectedSubnets,
      timeout: Duration.seconds(props.config.INTAKE_LAMBDA_TIMEOUT),
      ephemeralStorageSize: Size.gibibytes(
        props.config.INTAKE_LAMBDA_STORAGE_SIZE
      ),
      memorySize: props.config.INTAKE_LAMBDA_MEMORY_SIZE,
      environment: {
        OUTPUT_BUCKET: props.outputBucket.bucketName,
        OUTPUT_TOPIC: props.stacTopic.topicArn
      },
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
    props.inputTopic.addSubscription(new LambdaSubscription(this.function));
  }

  /**
   * Initializes the intake Lambda role.
   *
   * @param props - The IntakeFunction properties
   * @returns The intake Lambda role
   */
  private initializeRole(props: IntakeFunctionProps): IRole {
    if (
      props.config.INTAKE_LAMBDA_ROLE_NAME &&
      props.config.INTAKE_LAMBDA_ROLE_NAME !== undefined &&
      props.config.INTAKE_LAMBDA_ROLE_NAME !== ""
    ) {
      return Role.fromRoleName(
        this,
        "ImportedIntakeRole",
        props.config.INTAKE_LAMBDA_ROLE_NAME,
        { mutable: false }
      );
    }
    return new IntakeRole(this, "IntakeRole", {
      account: props.account,
      roleName: "IntakeLambdaRole"
    }).role;
  }

  /**
   * Creates the intake container.
   *
   * @param props - The IntakeFunction properties
   * @returns The intake container
   */
  private createContainer(props: IntakeFunctionProps): Container {
    return new Container(this, "IntakeContainer", {
      account: props.account,
      buildDockerImageCode: true,
      buildFromSource: props.config.BUILD_FROM_SOURCE,
      config: new ContainerConfig({
        CONTAINER_URI: props.config.INTAKE_CONTAINER_URI,
        CONTAINER_BUILD_PATH: props.config.CONTAINER_BUILD_PATH,
        CONTAINER_BUILD_TARGET: props.config.INTAKE_CONTAINER_BUILD_TARGET,
        CONTAINER_DOCKERFILE: props.config.INTAKE_CONTAINER_DOCKERFILE
      })
    });
  }
}
