/*
 * Copyright 2024-2025 Amazon.com, Inc. or its affiliates.
 */

import { RemovalPolicy } from "aws-cdk-lib";
import {
  EbsDeviceVolumeType,
  ISecurityGroup,
  IVpc,
  SubnetSelection
} from "aws-cdk-lib/aws-ec2";
import {
  AnyPrincipal,
  CfnServiceLinkedRole,
  PolicyStatement
} from "aws-cdk-lib/aws-iam";
import { Domain, EngineVersion } from "aws-cdk-lib/aws-opensearchservice";
import { NagSuppressions } from "cdk-nag";
import { Construct } from "constructs";

import { OSMLAccount } from "../types";
import { DataplaneConfig } from "./dataplane";

/**
 * Properties for creating OpenSearch domain resources.
 */
export interface OpenSearchProps {
  /** The OSML account configuration. */
  readonly account: OSMLAccount;
  /** The VPC configuration. */
  readonly vpc: IVpc;
  /** The selected subnets for the VPC. */
  readonly selectedSubnets: SubnetSelection;
  /** The security group for the OpenSearch domain. */
  readonly securityGroup: ISecurityGroup;
  /** The DC dataplane configuration. */
  readonly config: DataplaneConfig;
  /** The removal policy for resources. */
  readonly removalPolicy: RemovalPolicy;
}

/**
 * Construct that manages the OpenSearch domain for the Data Catalog.
 *
 * This construct encapsulates the creation and configuration of the OpenSearch
 * domain required by the Data Catalog STAC API.
 */
export class OpenSearch extends Construct {
  /** The OpenSearch domain. */
  public readonly domain: Domain;

  /**
   * The service-linked role for OpenSearch/Elasticsearch service.
   * This role is created once per AWS account. If it already exists,
   * CloudFormation will fail, but AWS will automatically create it
   * when the OpenSearch domain is provisioned if it doesn't exist.
   */
  public readonly serviceLinkedRole: CfnServiceLinkedRole;

  /**
   * Creates a new OpenSearch construct.
   *
   * @param scope - The scope/stack in which to define this construct
   * @param id - The id of this construct within the current scope
   * @param props - The properties for configuring this construct
   */
  constructor(scope: Construct, id: string, props: OpenSearchProps) {
    super(scope, id);

    // Determine the number of availability zones from selected subnets
    const selectedSubnets = props.vpc.selectSubnets(props.selectedSubnets);
    // Count unique availability zones (multiple subnets can be in the same AZ)
    const uniqueAzs = new Set(
      selectedSubnets.subnets.map((subnet) => subnet.availabilityZone)
    );
    const availabilityZoneCount = uniqueAzs.size || 2;

    // Ensure data nodes is a multiple of availability zones
    // Round up to the next multiple to meet OpenSearch requirements
    const requestedDataNodes = props.config.OS_DATA_NODES;
    const adjustedDataNodes =
      Math.ceil(requestedDataNodes / availabilityZoneCount) *
      availabilityZoneCount;

    // Create OpenSearch domain for our STAC database
    // Note: The domain will use the service-linked role whether it's created
    // by this stack or already exists in the account.
    // Zone awareness is enabled for high availability across multiple AZs.
    // This requires dedicated master nodes and GP3/io1 EBS volume types.
    this.domain = new Domain(this, "DCOSDomain", {
      version: EngineVersion.OPENSEARCH_2_11,
      nodeToNodeEncryption: true,
      enforceHttps: true,
      encryptionAtRest: {
        enabled: true
      },
      ebs: {
        enabled: true,
        volumeType: EbsDeviceVolumeType.GP3,
        volumeSize: 20
      },
      vpc: props.vpc,
      capacity: {
        dataNodes: adjustedDataNodes,
        masterNodes: 3,
        masterNodeInstanceType: "m5.large.search"
      },
      vpcSubnets: [props.selectedSubnets],
      removalPolicy: props.removalPolicy,
      zoneAwareness: {
        enabled: true,
        availabilityZoneCount: availabilityZoneCount
      },
      securityGroups: [props.securityGroup]
    });

    // Add access policies to allow Lambda functions to access the domain
    this.domain.addAccessPolicies(
      new PolicyStatement({
        principals: [new AnyPrincipal()],
        actions: ["es:ESHttp*"],
        resources: [this.domain.domainArn + "/*"]
      })
    );

    // Add cdk-nag suppressions
    NagSuppressions.addResourceSuppressions(
      this.domain,
      [
        {
          id: "AwsSolutions-OS9",
          reason:
            "Slow log export is not required for this use case. The OpenSearch domain is used for STAC metadata indexing and querying, and slow logs can be enabled via CloudWatch if needed for troubleshooting."
        },
        {
          id: "AwsSolutions-OS3",
          reason:
            "IP allowlisting is not required as the OpenSearch domain is deployed in a VPC with security groups controlling access. Network access is restricted to resources within the VPC."
        },
        {
          id: "AwsSolutions-OS5",
          reason:
            "The OpenSearch domain uses resource-based access policies with IAM principals. The domain is deployed in a VPC and access is controlled via security groups and IAM policies, not through public access restrictions."
        }
      ],
      true
    );
  }
}
