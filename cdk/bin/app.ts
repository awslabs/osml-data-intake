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

import { DataCatalogStack } from "../lib/data-catalog-stack";
import { IntegrationTestStack } from "../lib/integration-test-stack";
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
    deployment: deployment
  }
);

// -----------------------------------------------------------------------------
// Deploy the DataCatalogStack (includes data-intake components)
// -----------------------------------------------------------------------------

const dataCatalogStack = new DataCatalogStack(
  app,
  `${deployment.projectName}-Dataplane`,
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

// -----------------------------------------------------------------------------
// Deploy the IntegrationTestStack (if enabled)
// -----------------------------------------------------------------------------

if (deployment.deployIntegrationTests) {
  const integrationTestStack = new IntegrationTestStack(
    app,
    `${deployment.projectName}-IntegrationTest`,
    {
      env: {
        account: deployment.account.id,
        region: deployment.account.region
      },
      deployment: deployment,
      vpc: networkStack.network.vpc,
      selectedSubnets: networkStack.network.selectedSubnets,
      dataplane: dataCatalogStack.resources
    }
  );
  integrationTestStack.node.addDependency(dataCatalogStack);
}
