#!/usr/bin/env node

/*
 * Copyright 2025 Amazon.com, Inc. or its affiliates.
 */

/**
 * @file Entry point for the OSML Data Intake CDK application.
 *
 * This file bootstraps the CDK app, loads deployment configuration,
 * and instantiates the DataCatalogStack with validated parameters.
 *
 */

import { App } from "aws-cdk-lib";
import { IVpc, Vpc } from "aws-cdk-lib/aws-ec2";

import { DataCatalogStack } from "../lib/data-catalog-stack";
import { NetworkStack } from "../lib/network-stack";
import { loadDeploymentConfig } from "./deployment/load-deployment";

// -----------------------------------------------------------------------------
// Initialize CDK Application
// -----------------------------------------------------------------------------

const app = new App();

// -----------------------------------------------------------------------------
// Load the user provided deployment configuration.
// -----------------------------------------------------------------------------

const deployment = loadDeploymentConfig();

// -----------------------------------------------------------------------------
// Create VPC (only if importing existing VPC)
// -----------------------------------------------------------------------------

let vpc: IVpc | undefined;
if (deployment.networkConfig?.VPC_ID) {
  // Import existing VPC
  vpc = Vpc.fromLookup(app, "SharedVPC", {
    vpcId: deployment.networkConfig.VPC_ID
  });
}

// -----------------------------------------------------------------------------
// Deploy the network stack.
// -----------------------------------------------------------------------------

const networkStack = new NetworkStack(
  app,
  `${deployment.projectName}-Network`,
  {
    env: {
      account: deployment.account.id,
      region: deployment.account.region
    },
    deployment: deployment,
    vpc: vpc
  }
);

// -----------------------------------------------------------------------------
// Deploy the DataCatalogStack (includes data-intake components)
// -----------------------------------------------------------------------------

const dataCatalogStack = new DataCatalogStack(
  app,
  `${deployment.projectName}-DataCatalog`,
  {
    env: {
      account: deployment.account.id,
      region: deployment.account.region
    },
    deployment: deployment,
    vpc: networkStack.network.vpc,
    selectedSubnets: networkStack.network.selectedSubnets
  }
);
dataCatalogStack.node.addDependency(networkStack);
