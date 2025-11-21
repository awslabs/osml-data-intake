/*
 * Copyright 2024-2025 Amazon.com, Inc. or its affiliates.
 */

import { Duration, Size } from "aws-cdk-lib";
import { IVpc, SubnetSelection } from "aws-cdk-lib/aws-ec2";
import { IRole } from "aws-cdk-lib/aws-iam";
import {
  DockerImageFunction,
  Function,
  LoggingFormat
} from "aws-cdk-lib/aws-lambda";
import { Bucket } from "aws-cdk-lib/aws-s3";
import { ITopic } from "aws-cdk-lib/aws-sns";
import { LambdaSubscription } from "aws-cdk-lib/aws-sns-subscriptions";
import { Construct } from "constructs";

import { OSMLAccount } from "../types";
import { Container } from "./container";
import { DataplaneConfig } from "./dataplane";

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
  /** The IAM role for the Lambda function. */
  readonly lambdaRole: IRole;
  /** The intake container. */
  readonly intakeContainer: Container;
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

  /**
   * Creates a new IntakeFunction construct.
   *
   * @param scope - The scope/stack in which to define this construct
   * @param id - The id of this construct within the current scope
   * @param props - The properties for configuring this construct
   */
  constructor(scope: Construct, id: string, props: IntakeFunctionProps) {
    super(scope, id);

    // Create the intake Lambda function
    this.function = new DockerImageFunction(this, "DataCatalogIntakeFunction", {
      functionName: "data-catalog-intake",
      code: props.intakeContainer.dockerImageCode,
      role: props.lambdaRole,
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
    this.function.node.addDependency(props.intakeContainer);

    // Subscribe Lambda function to the SNS topic
    props.inputTopic.addSubscription(new LambdaSubscription(this.function));
  }
}
