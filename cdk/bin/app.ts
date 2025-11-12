#!/usr/bin/env node

/*
 * Copyright 2023-2025 Amazon.com, Inc. or its affiliates.
 */

import { App } from "aws-cdk-lib";

import { DataIntakeStack } from "../lib/data-intake-stack";
import { DataCatalogStack } from "../lib/data-catalog-stack";
import { NetworkStack } from "../lib/network-stack";
import { loadDeployment } from "./deployment/load-deployment";

// Initialize the CDK app
const app = new App();

// Load deployment configuration
const deployment = loadDeployment();

// Create the network stack first (required by data intake stack)
const networkStack = new NetworkStack(app, `${deployment.projectName}-Network`, {
  account: deployment.account,
  config: deployment.networkConfig,
  env: {
    account: deployment.account.id,
    region: deployment.account.region
  },
  terminationProtection: deployment.account.prodLike
});

// Create the data intake stack
const dataIntakeStack = new DataIntakeStack(app, `${deployment.projectName}-DataIntake`, {
  account: deployment.account,
  vpc: networkStack.vpc,
  config: deployment.dataplaneConfig,
  env: {
    account: deployment.account.id,
    region: deployment.account.region
  },
  terminationProtection: deployment.account.prodLike
});

// Create the data catalog stack
const dataCatalogStack = new DataCatalogStack(app, `${deployment.projectName}-DataCatalog`, {
  account: deployment.account,
  vpc: networkStack.vpc,
  env: {
    account: deployment.account.id,
    region: deployment.account.region
  },
  terminationProtection: deployment.account.prodLike
});

// Ensure stacks depend on the network stack
dataIntakeStack.addDependency(networkStack);
dataCatalogStack.addDependency(networkStack);
