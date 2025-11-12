/*
 * Copyright 2023-2025 Amazon.com, Inc. or its affiliates.
 */

import { RemovalPolicy } from "aws-cdk-lib";
import { ISecurityGroup, SecurityGroup } from "aws-cdk-lib/aws-ec2";
import {
  AnyPrincipal,
  CfnServiceLinkedRole,
  PolicyStatement
} from "aws-cdk-lib/aws-iam";
import {
  Domain,
  EngineVersion,
  TLSSecurityPolicy
} from "aws-cdk-lib/aws-opensearchservice";
import { Construct } from "constructs";

import { Account } from "../shared/osml-account";
import { OSMLVpc } from "../shared/osml-vpc";

/**
 * Properties for configuring the DCOpenSearchDomain Construct.
 */
export interface DCOpenSearchDomainProps {
  /**
   * The deployment account.
   */
  account: Account;

  /**
   * The VPC configuration for the OpenSearch domain.
   */
  vpc: OSMLVpc;
}

/**
 * Represents the DCOpenSearchDomain construct for data catalog search capabilities.
 */
export class DCOpenSearchDomain extends Construct {
  /**
   * The OpenSearch domain instance.
   */
  public domain: Domain;

  /**
   * The security group for the OpenSearch domain.
   */
  public securityGroup: ISecurityGroup;

  /**
   * The removal policy for the domain.
   */
  public removalPolicy: RemovalPolicy;

  /**
   * Creates an instance of DCOpenSearchDomain.
   */
  constructor(scope: Construct, id: string, props: DCOpenSearchDomainProps) {
    super(scope, id);

    // Set removal policy based on account type
    this.removalPolicy = props.account.prodLike
      ? RemovalPolicy.RETAIN
      : RemovalPolicy.DESTROY;

    // Create service linked role for OpenSearch
    new CfnServiceLinkedRole(this, "OpensearchServiceLinkedRole", {
      awsServiceName: "es.amazonaws.com"
    });

    // Create security group for OpenSearch domain
    this.securityGroup = new SecurityGroup(this, "DCOSSecurityGroup", {
      vpc: props.vpc.vpc,
      description: "Security group for Data Catalog OpenSearch domain",
      allowAllOutbound: true
    });

    // Get available subnets and determine AZ count
    const availableSubnets = props.vpc.selectedSubnets.subnets;
    const azCount = Math.min(availableSubnets.length, 2); // Use max 2 AZs for compatibility
    const dataNodes = azCount * 2; // 2 nodes per AZ

    // Create OpenSearch domain
    this.domain = new Domain(this, id, {
      version: EngineVersion.OPENSEARCH_2_11,
      capacity: {
        dataNodes: dataNodes,
        dataNodeInstanceType: "r5.large.search"
      },
      ebs: {
        volumeSize: 10
      },
      zoneAwareness: {
        enabled: azCount > 1,
        availabilityZoneCount: azCount > 1 ? azCount : undefined
      },
      nodeToNodeEncryption: true,
      encryptionAtRest: {
        enabled: true
      },
      enforceHttps: true,
      tlsSecurityPolicy: TLSSecurityPolicy.TLS_1_2,
      vpc: props.vpc.vpc,
      vpcSubnets: [props.vpc.selectedSubnets],
      securityGroups: [this.securityGroup],
      removalPolicy: this.removalPolicy
    });

    // Add access policies to allow Lambda functions to access OpenSearch
    this.domain.addAccessPolicies(
      new PolicyStatement({
        principals: [new AnyPrincipal()],
        actions: ["es:ESHttp*"],
        resources: [this.domain.domainArn + "/*"]
      })
    );
  }
}
