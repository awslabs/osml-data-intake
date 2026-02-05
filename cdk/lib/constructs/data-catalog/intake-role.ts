/*
 * Copyright 2023-2026 Amazon.com, Inc. or its affiliates.
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
}

/**
 * Construct that manages the Lambda role for the intake function.
 *
 * This role has permissions for:
 * - S3 read/write operations (for processing intake data)
 * - SNS publish/subscribe (for receiving intake requests and publishing STAC items)
 * - CloudFormation list exports (for discovering STAC API URL)
 * - Lambda basic execution and VPC access
 */
export class IntakeRole extends Construct {
  /**
   * The AWS IAM role associated with this Lambda role.
   */
  public role: IRole;

  /**
   * The AWS partition to be used for this Lambda role.
   */
  public partition: string;

  /**
   * Creates an IntakeRole construct.
   * @param {Construct} scope - The scope/stack in which to define this construct.
   * @param {string} id - The id of this construct within the current scope.
   * @param {LambdaRoleProps} props - The properties of this construct.
   * @returns IntakeRole - The IntakeRole construct.
   */
  constructor(scope: Construct, id: string, props: LambdaRoleProps) {
    super(scope, id);

    // Determine the AWS partition based on the provided AWS region
    this.partition = region_info.Fact.find(
      props.account.region,
      region_info.FactName.PARTITION
    )!;

    // Create an AWS IAM role for the Lambda function
    const role = new Role(this, "IntakeRole", {
      roleName: props.roleName,
      assumedBy: new CompositePrincipal(
        new ServicePrincipal("lambda.amazonaws.com")
      ),
      description:
        "Allows the OversightML data catalog intake Lambda to access necessary AWS services (SNS publish/subscribe, S3 read/write)"
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
    const policy = new ManagedPolicy(this, "IntakePolicy", {
      managedPolicyName: `${props.roleName}Policy`
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
          "s3:GetObjectTagging",
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

    // Add permissions for CloudFormation to discover STAC API URL from exports
    policy.addStatements(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ["cloudformation:ListExports"],
        resources: ["*"]
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
            "Wildcard permissions are required for S3 and SNS as the intake Lambda needs to access multiple buckets and publish to any topic in the account. CloudFormation ListExports is needed to discover the STAC API URL. The Lambda is deployed in a VPC with restricted network access.",
          appliesTo: [
            `Resource::arn:${this.partition}:s3:::*`,
            `Resource::arn:${this.partition}:sns:${props.account.region}:${props.account.id}:*`,
            "Resource::*"
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
            "Wildcard permissions are required for S3 and SNS as the intake Lambda needs to access multiple buckets and publish to any topic in the account. CloudFormation ListExports is needed to discover the STAC API URL. The Lambda is deployed in a VPC with restricted network access.",
          appliesTo: [
            `Resource::arn:${this.partition}:s3:::*`,
            `Resource::arn:${this.partition}:sns:${props.account.region}:${props.account.id}:*`,
            "Resource::*"
          ]
        }
      ],
      true
    );

    // Set the role on class
    this.role = role;
  }
}
