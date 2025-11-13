/*
 * Copyright 2023-2024 Amazon.com, Inc. or its affiliates.
 */

import { region_info } from "aws-cdk-lib";
import {
  CompositePrincipal,
  Effect,
  IRole,
  ManagedPolicy,
  PolicyStatement,
  Role,
  ServicePrincipal
} from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";

import { OSMLAccount } from "../../types";

/**
 * Represents the properties required to define a data catalog Lambda role.
 */
export interface DCLambdaRoleProps {
  /**
   * The deployment account associated with this role.
   */
  account: OSMLAccount;

  /**
   * The name to give to the role.
   */
  roleName: string;
}

/**
 * Creates a DCLambdaRole construct for Data Catalog Lambda functions.
 */
export class DCLambdaRole extends Construct {
  /**
   * The AWS IAM role associated with this DCLambdaRole.
   */
  public role: IRole;

  /**
   * The AWS partition to be used for this DCLambdaRole.
   */
  public partition: string;

  /**
   * Creates a DCLambdaRole construct.
   */
  constructor(scope: Construct, id: string, props: DCLambdaRoleProps) {
    super(scope, id);

    // Determine the AWS partition based on the provided AWS region
    this.partition = region_info.Fact.find(
      props.account.region,
      region_info.FactName.PARTITION
    )!;

    // Create an AWS IAM role for the Data Catalog Lambda Functions
    const role = new Role(this, "DCLambdaRole", {
      roleName: props.roleName,
      assumedBy: new CompositePrincipal(
        new ServicePrincipal("lambda.amazonaws.com")
      ),
      description:
        "Allows the Data Catalog Lambda to access necessary AWS services (SNS, S3, OpenSearch, ...)",
      managedPolicies: [
        ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole"
        ),
        ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaVPCAccessExecutionRole"
        )
      ]
    });

    // Create a managed policy to attach to the role
    const policy = new ManagedPolicy(this, "DCLambdaPolicy", {
      managedPolicyName: "DCLambdaPolicy"
    });

    // Add permissions for S3 permissions
    policy.addStatements(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          "s3:GetBucketAcl",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:GetObjectAcl",
          "s3:PutObject",
          "s3:DeleteObject"
        ],
        resources: [`arn:${this.partition}:s3:::*`]
      })
    );

    // Add permissions for SNS topics
    policy.addStatements(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ["sns:Publish", "sns:Subscribe"],
        resources: [
          `arn:${this.partition}:sns:${props.account.region}:${props.account.id}:*`
        ]
      })
    );

    // Attach policy to the role
    role.addManagedPolicy(policy);

    // Set the role on class
    this.role = role;
  }
}
