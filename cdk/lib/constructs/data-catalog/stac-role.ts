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

  /**
   * The OpenSearch domain ARN (optional).
   * If provided, the role will be granted permissions to access OpenSearch.
   *
   * @type {string | undefined}
   */
  openSearchDomainArn?: string;
}

/**
 * Construct that manages the Lambda role for the STAC API function.
 *
 * This role has permissions for:
 * - S3 read-only operations (for serving STAC items/assets)
 * - OpenSearch access (for querying STAC metadata)
 * - Lambda basic execution and VPC access
 * - No SNS permissions (not needed for read-only API)
 */
export class StacRole extends Construct {
  /**
   * The AWS IAM role associated with this Lambda role.
   */
  public role: IRole;

  /**
   * The AWS partition to be used for this Lambda role.
   */
  public partition: string;

  /**
   * Creates a StacRole construct.
   * @param {Construct} scope - The scope/stack in which to define this construct.
   * @param {string} id - The id of this construct within the current scope.
   * @param {LambdaRoleProps} props - The properties of this construct.
   * @returns StacRole - The StacRole construct.
   */
  constructor(scope: Construct, id: string, props: LambdaRoleProps) {
    super(scope, id);

    // Determine the AWS partition based on the provided AWS region
    this.partition = region_info.Fact.find(
      props.account.region,
      region_info.FactName.PARTITION
    )!;

    // Create an AWS IAM role for the Lambda function
    const role = new Role(this, "StacRole", {
      roleName: props.roleName,
      assumedBy: new CompositePrincipal(
        new ServicePrincipal("lambda.amazonaws.com")
      ),
      description:
        "Allows the OversightML data catalog STAC API Lambda to access necessary AWS services (S3 read-only)"
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
    const policy = new ManagedPolicy(this, "StacPolicy", {
      managedPolicyName: `${props.roleName}Policy`
    });

    // Add permissions for S3 read-only operations (needed for serving STAC items/assets)
    policy.addStatements(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          "s3:GetBucketAcl",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:GetObjectAcl"
        ],
        resources: [`arn:${this.partition}:s3:::*`]
      })
    );

    // Add permissions for OpenSearch access (needed for querying STAC metadata)
    if (props.openSearchDomainArn) {
      policy.addStatements(
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: ["es:ESHttp*"],
          resources: [`${props.openSearchDomainArn}/*`]
        })
      );
    }

    // Attach policy to the role
    role.addManagedPolicy(policy);

    // Build appliesTo array for IAM5 suppressions
    // Note: OpenSearch domain ARN is a token and cannot be matched exactly in appliesTo
    const iam5Resources = [`Resource::arn:${this.partition}:s3:::*`];

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
            "Wildcard permissions are required for S3 as the STAC API Lambda needs to serve STAC items/assets from multiple buckets. OpenSearch permissions are scoped to the specific domain. The Lambda is deployed in a VPC with restricted network access.",
          appliesTo: iam5Resources
        }
      ],
      true
    );

    // Suppress IAM5 for policy - without appliesTo for OpenSearch since domain ARN is a token
    NagSuppressions.addResourceSuppressions(
      policy,
      [
        {
          id: "AwsSolutions-IAM5",
          reason:
            "Wildcard permissions are required for S3 as the STAC API Lambda needs to serve STAC items/assets from multiple buckets. OpenSearch permissions (es:ESHttp* and resource wildcard) are scoped to the specific domain ARN but cannot be matched in appliesTo due to token resolution. The Lambda is deployed in a VPC with restricted network access."
        }
      ],
      true
    );

    // Set the role on class
    this.role = role;
  }
}
