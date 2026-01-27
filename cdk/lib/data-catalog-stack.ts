/*
 * Copyright 2024-2026 Amazon.com, Inc. or its affiliates.
 */

import { App, CfnOutput, Environment, Stack, StackProps } from "aws-cdk-lib";
import { IVpc, SubnetSelection } from "aws-cdk-lib/aws-ec2";
import { NagSuppressions } from "cdk-nag";

import { DeploymentConfig } from "../bin/deployment/load-deployment";
import {
  Dataplane,
  DataplaneConfig
} from "./constructs/data-catalog/dataplane";

export interface DataCatalogStackProps extends StackProps {
  readonly env: Environment;
  readonly deployment: DeploymentConfig;
  readonly vpc: IVpc; // VPC is now required and provided by NetworkStack
  readonly selectedSubnets: SubnetSelection; // Selected subnets from NetworkStack
}

export class DataCatalogStack extends Stack {
  public resources: Dataplane;
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
      terminationProtection: props.deployment.account.prodLike || false,
      ...props
    });

    // Store deployment config for use in other methods
    this.deployment = props.deployment;

    // Use the provided VPC from NetworkStack
    this.vpc = props.vpc;

    // Create the data catalog application dataplane using the VPC
    const dataplaneConfig = props.deployment.dataplaneConfig
      ? new DataplaneConfig(props.deployment.dataplaneConfig)
      : undefined;
    this.resources = new Dataplane(this, "Dataplane", {
      account: props.deployment.account,
      vpc: this.vpc,
      selectedSubnets: props.selectedSubnets,
      config: dataplaneConfig
    });

    // Add CloudFormation output for the STAC Lambda ARN
    new CfnOutput(this, "StacLambdaArn", {
      value: this.resources.stacFunction.function.functionArn,
      description: "ARN of the STAC API Lambda function",
      exportName: `${this.deployment.projectName}-StacLambdaArn`
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
      },
      {
        id: "AwsSolutions-IAM5",
        reason:
          "LogRetention Lambda functions created by CDK require wildcard permissions to manage log groups across the account. This is a standard CDK custom resource that manages log group retention policies and requires broad permissions to function correctly.",
        appliesTo: ["Resource::*"]
      }
    ]);
  }
}
