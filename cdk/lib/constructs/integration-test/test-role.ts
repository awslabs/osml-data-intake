/*
 * Copyright 2024-2025 Amazon.com, Inc. or its affiliates.
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
import { IFunction } from "aws-cdk-lib/aws-lambda";
import { NagSuppressions } from "cdk-nag";
import { Construct } from "constructs";

import { OSMLAccount } from "../types";

/**
 * Properties for creating a Lambda role.
 */
export interface LambdaRoleProps {
  /**
   * The OSML deployment account associated with this role.
   *
   * @type {OSMLAccount}
   */
  account: OSMLAccount;

  /**
   * The name to give to the role.
   *
   * @type {string}
   */
  roleName: string;

  /**
   * The STAC Lambda function to allow invocation.
   *
   * @type {IFunction}
   */
  stacFunction: IFunction;

  /**
   * The input bucket ARN for test image uploads.
   *
   * @type {string}
   */
  inputBucketArn: string;
}

/**
 * Construct that manages the Lambda role for the integration test function.
 *
 * This role has permissions for:
 * - S3 read/write operations (for uploading test images)
 * - SNS publish (for publishing test messages to intake topic)
 * - Lambda invoke (for invoking STAC function to retrieve items)
 * - Lambda basic execution and VPC access
 */
export class IntegrationTestRole extends Construct {
  /**
   * The AWS IAM role associated with this Lambda role.
   */
  public role: IRole;

  /**
   * The AWS partition to be used for this Lambda role.
   */
  public partition: string;

  /**
   * Creates an IntegrationTestRole construct.
   * @param {Construct} scope - The scope/stack in which to define this construct.
   * @param {string} id - The id of this construct within the current scope.
   * @param {LambdaRoleProps} props - The properties of this construct.
   * @returns IntegrationTestRole - The IntegrationTestRole construct.
   */
  constructor(scope: Construct, id: string, props: LambdaRoleProps) {
    super(scope, id);

    // Determine the AWS partition based on the provided AWS region
    this.partition = region_info.Fact.find(
      props.account.region,
      region_info.FactName.PARTITION
    )!;

    // Create an AWS IAM role for the Lambda function
    const role = new Role(this, "IntegrationTestRole", {
      roleName: props.roleName,
      assumedBy: new CompositePrincipal(
        new ServicePrincipal("lambda.amazonaws.com")
      ),
      description:
        "Allows the OversightML data catalog integration test Lambda to access necessary AWS services (S3, SNS, Lambda)"
    });

    // Add AWS managed policies for Lambda execution
    role.addManagedPolicy(
      ManagedPolicy.fromManagedPolicyArn(
        this,
        "LambdaBasicExecutionPolicy",
        `arn:${this.partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole`
      )
    );
    role.addManagedPolicy(
      ManagedPolicy.fromManagedPolicyArn(
        this,
        "LambdaVPCAccessExecutionPolicy",
        `arn:${this.partition}:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole`
      )
    );

    // Create a managed policy to attach to the role
    const policy = new ManagedPolicy(this, "IntegrationTestPolicy", {
      managedPolicyName: `${props.roleName}Policy`
    });

    // Add permissions for S3 operations on input bucket
    policy.addStatements(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
        resources: [`${props.inputBucketArn}/*`]
      })
    );

    policy.addStatements(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ["s3:ListBucket"],
        resources: [props.inputBucketArn]
      })
    );

    // Add permissions for SNS publish to intake topic
    policy.addStatements(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ["sns:Publish"],
        resources: [
          `arn:${this.partition}:sns:${props.account.region}:${props.account.id}:*`
        ]
      })
    );

    // Add permissions to invoke STAC Lambda function
    policy.addStatements(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ["lambda:InvokeFunction"],
        resources: [props.stacFunction.functionArn]
      })
    );

    // Attach policy to the role
    role.addManagedPolicy(policy);

    // Add cdk-nag suppressions
    NagSuppressions.addResourceSuppressions(
      role,
      [
        {
          id: "AwsSolutions-IAM4",
          reason:
            "AWS managed policies are required for Lambda basic execution and VPC access. These are standard AWS managed policies with well-defined permissions.",
          appliesTo: [
            `Policy::arn:${this.partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole`,
            `Policy::arn:${this.partition}:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole`
          ]
        },
        {
          id: "AwsSolutions-IAM5",
          reason:
            "Wildcard permissions for SNS are required as the integration test Lambda needs to publish to the intake topic. The Lambda is deployed in a VPC with restricted network access.",
          appliesTo: [
            `Resource::arn:${this.partition}:sns:${props.account.region}:${props.account.id}:*`
          ]
        }
      ],
      true
    );

    NagSuppressions.addResourceSuppressions(
      policy,
      [
        {
          id: "AwsSolutions-IAM5",
          reason:
            "Wildcard permissions for SNS are required as the integration test Lambda needs to publish to the intake topic. The Lambda is deployed in a VPC with restricted network access.",
          appliesTo: [
            `Resource::arn:${this.partition}:sns:${props.account.region}:${props.account.id}:*`
          ]
        }
      ],
      true
    );

    // Set the role on class
    this.role = role;
  }
}
