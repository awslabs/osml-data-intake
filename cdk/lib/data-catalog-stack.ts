/*
 * Copyright 2024-2025 Amazon.com, Inc. or its affiliates.
 */

import { App, Environment, Stack, StackProps } from "aws-cdk-lib";
import { IVpc, SubnetSelection } from "aws-cdk-lib/aws-ec2";
import { ITopic } from "aws-cdk-lib/aws-sns";
import { NagSuppressions } from "cdk-nag";

import { DeploymentConfig } from "../bin/deployment/load-deployment";
import {
  DCDataplane,
  DCDataplaneConfig
} from "./constructs/data-catalog/dataplane";

export interface DataCatalogStackProps extends StackProps {
  readonly env: Environment;
  readonly deployment: DeploymentConfig;
  readonly vpc: IVpc; // VPC is now required and provided by NetworkStack
  readonly selectedSubnets: SubnetSelection; // Selected subnets from NetworkStack
  readonly ingestTopic?: ITopic; // Optional ingest topic from DataIntakeStack
}

export class DataCatalogStack extends Stack {
  public resources: DCDataplane;
  public vpc: IVpc;
  public deployment: DeploymentConfig;

  /**
   * Constructor for the data catalog dataplane cdk stack
   * @param parent the parent cdk app object
   * @param name the name of the stack to be created in the parent app object.
   * @param props the properties required to create the stack.
   * @returns the created DataCatalogStack object
   */
  constructor(parent: App, name: string, props: DataCatalogStackProps) {
    super(parent, name, {
      terminationProtection: props.deployment.account.prodLike,
      ...props
    });

    // Store deployment config for use in other methods
    this.deployment = props.deployment;

    // Use the provided VPC from NetworkStack
    this.vpc = props.vpc;

    // Create the data catalog application dataplane using the VPC
    const dataplaneConfig = props.deployment.dataplaneConfig
      ? new DCDataplaneConfig(props.deployment.dataplaneConfig)
      : undefined;
    this.resources = new DCDataplane(this, "Dataplane", {
      account: props.deployment.account,
      vpc: this.vpc,
      selectedSubnets: props.selectedSubnets,
      ingestTopic: props.ingestTopic, // Use provided ingest topic from DataIntakeStack
      config: dataplaneConfig
    });

    // Add cdk-nag suppressions for custom resources created by OpenSearch domain
    // These are automatically created by CDK for managing OpenSearch access policies
    NagSuppressions.addStackSuppressions(this, [
      {
        id: "AwsSolutions-IAM4",
        reason:
          "AWS managed policies are required for custom resource Lambda execution roles. These are standard AWS managed policies used by CDK custom resources.",
        appliesTo: [
          "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        ]
      },
      {
        id: "AwsSolutions-L1",
        reason:
          "Custom resource Lambda functions use a specific runtime version required by CDK. The runtime version is managed by the CDK framework and cannot be changed."
      }
    ]);
  }
}
