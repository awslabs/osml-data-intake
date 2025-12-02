/*
 * Copyright 2024-2025 Amazon.com, Inc. or its affiliates.
 */

import {
  App,
  Environment,
  RemovalPolicy,
  Stack,
  StackProps
} from "aws-cdk-lib";
import { IVpc, SubnetSelection } from "aws-cdk-lib/aws-ec2";
import { Bucket, BucketEncryption } from "aws-cdk-lib/aws-s3";

import { DeploymentConfig } from "../bin/deployment/load-deployment";
import { Dataplane } from "./constructs/data-catalog/dataplane";
import {
  IntegrationTestConfig,
  IntegrationTestFunction
} from "./constructs/integration-test/test-function";

export interface IntegrationTestStackProps extends StackProps {
  readonly env: Environment;
  readonly deployment: DeploymentConfig;
  readonly vpc: IVpc;
  readonly selectedSubnets: SubnetSelection;
  /** The dataplane construct to access resources from. */
  readonly dataplane: Dataplane;
}

export class IntegrationTestStack extends Stack {
  public readonly integrationTestFunction: IntegrationTestFunction;
  public readonly inputBucket: Bucket;

  /**
   * Constructor for the integration test CDK stack
   * @param parent the parent cdk app object
   * @param name the name of the stack to be created in the parent app object.
   * @param props the properties required to create the stack.
   * @returns the created IntegrationTestStack object
   */
  constructor(parent: App, name: string, props: IntegrationTestStackProps) {
    super(parent, name, {
      terminationProtection: props.deployment.account.prodLike,
      ...props
    });

    // Create the integration test configuration
    const integrationTestConfig = props.deployment.integrationTestConfig
      ? new IntegrationTestConfig(props.deployment.integrationTestConfig)
      : new IntegrationTestConfig();

    // Create the input bucket for test images
    this.inputBucket = new Bucket(this, "InputBucket", {
      bucketName: `${props.deployment.account.id}-data-catalog-test-bucket`,
      encryption: BucketEncryption.S3_MANAGED,
      removalPolicy: props.deployment.account.prodLike
        ? RemovalPolicy.RETAIN
        : RemovalPolicy.DESTROY,
      autoDeleteObjects: !props.deployment.account.prodLike
    });

    // Create the integration test Lambda function
    this.integrationTestFunction = new IntegrationTestFunction(
      this,
      "IntegrationTestFunction",
      {
        account: props.deployment.account,
        vpc: props.vpc,
        selectedSubnets: props.selectedSubnets,
        inputBucket: this.inputBucket,
        inputTopic: props.dataplane.inputTopic,
        stacFunction: props.dataplane.stacFunction.function,
        securityGroup: props.dataplane.securityGroup,
        config: integrationTestConfig,
        removalPolicy: props.deployment.account.prodLike
          ? RemovalPolicy.RETAIN
          : RemovalPolicy.DESTROY
      }
    );
  }
}
