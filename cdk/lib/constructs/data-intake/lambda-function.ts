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

import { Container } from "../data-catalog/container";
import { OSMLAccount } from "../types";
import { DIDataplaneConfig } from "./dataplane";

/**
 * Properties for creating Lambda function resources.
 */
export interface LambdaFunctionProps {
  /** The OSML account configuration. */
  readonly account: OSMLAccount;
  /** The VPC configuration. */
  readonly vpc: IVpc;
  /** The selected subnets for the VPC. */
  readonly selectedSubnets: SubnetSelection;
  /** The IAM role for the Lambda function. */
  readonly lambdaRole: IRole;
  /** The container for the Lambda function. */
  readonly container: Container;
  /** The S3 output bucket. */
  readonly outputBucket: Bucket;
  /** The STAC SNS topic. */
  readonly stacTopic: ITopic;
  /** The input SNS topic. */
  readonly inputTopic: ITopic;
  /** The security group for the Lambda function (optional). */
  readonly securityGroup?: import("aws-cdk-lib/aws-ec2").ISecurityGroup;
  /** The DI dataplane configuration. */
  readonly config: DIDataplaneConfig;
}

/**
 * Construct that manages the Lambda function resource for the Data Intake.
 *
 * This construct encapsulates the creation and configuration of the Lambda
 * function required by the Data Intake.
 */
export class LambdaFunction extends Construct {
  /** The Lambda function for data intake. */
  public readonly lambdaFunction: Function;

  /**
   * Creates a new LambdaFunction construct.
   *
   * @param scope - The scope/stack in which to define this construct
   * @param id - The id of this construct within the current scope
   * @param props - The properties for configuring this construct
   */
  constructor(scope: Construct, id: string, props: LambdaFunctionProps) {
    super(scope, id);

    // Create the Lambda function with a container image
    this.lambdaFunction = new DockerImageFunction(this, "DataIntakeFunction", {
      code: props.container.dockerImageCode,
      timeout: Duration.seconds(props.config.LAMBDA_TIMEOUT),
      functionName: props.config.LAMBDA_FUNCTION_NAME,
      environment: {
        OUTPUT_BUCKET: props.outputBucket.bucketName,
        OUTPUT_TOPIC: props.stacTopic.topicArn
      },
      memorySize: props.config.LAMBDA_MEMORY_SIZE,
      ephemeralStorageSize: Size.gibibytes(props.config.LAMBDA_STORAGE_SIZE),
      securityGroups: props.securityGroup ? [props.securityGroup] : [],
      vpc: props.vpc,
      vpcSubnets: props.selectedSubnets,
      role: props.lambdaRole,
      loggingFormat: LoggingFormat.JSON
    });
    this.lambdaFunction.node.addDependency(props.container);

    // Subscribe Lambda function to the SNS topic
    props.inputTopic.addSubscription(
      new LambdaSubscription(this.lambdaFunction)
    );
  }
}
