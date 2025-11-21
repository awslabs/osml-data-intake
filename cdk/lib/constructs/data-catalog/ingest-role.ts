/*
 * Copyright 2023-2025 Amazon.com, Inc. or its affiliates.
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
 * Construct that manages the Lambda role for the ingest function.
 *
 * This role has permissions for:
 * - S3 read/write operations (for ingesting data)
 * - SNS subscribe (for receiving ingest notifications)
 * - Lambda basic execution and VPC access
 */
export class IngestRole extends Construct {
  /**
   * The AWS IAM role associated with this Lambda role.
   */
  public role: IRole;

  /**
   * The AWS partition to be used for this Lambda role.
   */
  public partition: string;

  /**
   * Creates an IngestRole construct.
   * @param {Construct} scope - The scope/stack in which to define this construct.
   * @param {string} id - The id of this construct within the current scope.
   * @param {LambdaRoleProps} props - The properties of this construct.
   * @returns IngestRole - The IngestRole construct.
   */
  constructor(scope: Construct, id: string, props: LambdaRoleProps) {
    super(scope, id);

    // Determine the AWS partition based on the provided AWS region
    this.partition = region_info.Fact.find(
      props.account.region,
      region_info.FactName.PARTITION
    )!;

    // Create an AWS IAM role for the Lambda function
    const role = new Role(this, "IngestRole", {
      roleName: props.roleName,
      assumedBy: new CompositePrincipal(
        new ServicePrincipal("lambda.amazonaws.com")
      ),
      description:
        "Allows the OversightML data catalog ingest Lambda to access necessary AWS services (SNS subscribe, S3 read/write)"
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
    const policy = new ManagedPolicy(this, "IngestPolicy", {
      managedPolicyName: `${props.roleName}Policy`
    });

    // Add permissions for S3 read/write operations (needed for ingesting data)
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

    // Add permissions for SNS subscribe (needed to receive ingest notifications)
    policy.addStatements(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ["sns:Subscribe"],
        resources: [
          `arn:${this.partition}:sns:${props.account.region}:${props.account.id}:*`
        ]
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
            "Wildcard permissions are required for S3 and SNS as the ingest Lambda needs to access multiple buckets and subscribe to any ingest topic in the account. The Lambda is deployed in a VPC with restricted network access.",
          appliesTo: [
            `Resource::arn:${this.partition}:s3:::*`,
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
            "Wildcard permissions are required for S3 and SNS as the ingest Lambda needs to access multiple buckets and subscribe to any ingest topic in the account. The Lambda is deployed in a VPC with restricted network access.",
          appliesTo: [
            `Resource::arn:${this.partition}:s3:::*`,
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
