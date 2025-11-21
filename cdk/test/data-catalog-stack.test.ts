/*
 * Copyright 2025 Amazon.com, Inc. or its affiliates.
 */

/**
 * Unit tests for DataCatalogStack.
 */

import "source-map-support/register";

import { App, Aspects, Stack } from "aws-cdk-lib";
import { Annotations, Match, Template } from "aws-cdk-lib/assertions";
import { SubnetSelection, SubnetType } from "aws-cdk-lib/aws-ec2";
import { AwsSolutionsChecks } from "cdk-nag";

import { DataCatalogStack } from "../lib/data-catalog-stack";
import {
  createTestApp,
  createTestDeploymentConfig,
  createTestEnvironment,
  createTestVpc,
  generateNagReport
} from "./test-utils";

describe("DataCatalogStack", () => {
  let app: App;
  let deploymentConfig: ReturnType<typeof createTestDeploymentConfig>;
  let networkStack: Stack;
  let vpc: ReturnType<typeof createTestVpc>;
  let selectedSubnets: SubnetSelection;

  beforeEach(() => {
    app = createTestApp();
    deploymentConfig = createTestDeploymentConfig();
    networkStack = new Stack(app, "NetworkStack", {
      env: createTestEnvironment()
    });
    vpc = createTestVpc(networkStack);
    selectedSubnets = vpc.selectSubnets({
      subnetType: SubnetType.PRIVATE_WITH_EGRESS
    });
  });

  test("creates stack with correct properties", () => {
    const stack = new DataCatalogStack(app, "TestDataCatalogStack", {
      env: createTestEnvironment(),
      deployment: deploymentConfig,
      vpc: vpc,
      selectedSubnets: selectedSubnets
    });

    // Stack should exist and have correct termination protection
    expect(stack.terminationProtection).toBe(false);

    // VPC should be stored
    expect(stack.vpc).toBe(vpc);
  });

  test("sets termination protection when prodLike is true", () => {
    const prodDeploymentConfig = createTestDeploymentConfig({
      account: {
        id: "123456789012",
        region: "us-west-2",
        prodLike: true,
        isAdc: false
      }
    });

    const stack = new DataCatalogStack(app, "TestDataCatalogStack", {
      env: createTestEnvironment(),
      deployment: prodDeploymentConfig,
      vpc: vpc,
      selectedSubnets: selectedSubnets
    });

    expect(stack.terminationProtection).toBe(true);
  });

  test("creates dataplane construct", () => {
    const stack = new DataCatalogStack(app, "TestDataCatalogStack", {
      env: createTestEnvironment(),
      deployment: deploymentConfig,
      vpc: vpc,
      selectedSubnets: selectedSubnets
    });

    // Dataplane should be created
    expect(stack.resources).toBeDefined();

    const template = Template.fromStack(stack);

    // Stack should have resources (the dataplane creates various resources)
    // Check that the stack has been synthesized successfully
    expect(template).toBeDefined();
  });

  test("uses provided VPC from network stack", () => {
    const stack = new DataCatalogStack(app, "TestDataCatalogStack", {
      env: createTestEnvironment(),
      deployment: deploymentConfig,
      vpc: vpc,
      selectedSubnets: selectedSubnets
    });

    // VPC should be the same instance
    expect(stack.vpc).toBe(vpc);
  });

  test("creates stack with custom dataplane config", () => {
    const dataplaneConfigPartial = {
      BUILD_FROM_SOURCE: true,
      LAMBDA_MEMORY_SIZE: 8192
    };

    const deploymentWithConfig = createTestDeploymentConfig({
      dataplaneConfig: dataplaneConfigPartial
    });

    const stack = new DataCatalogStack(app, "TestDataCatalogStack", {
      env: createTestEnvironment(),
      deployment: deploymentWithConfig,
      vpc: vpc,
      selectedSubnets: selectedSubnets
    });

    // Stack should be created successfully
    expect(stack).toBeDefined();
    expect(stack.resources).toBeDefined();
  });
});

describe("cdk-nag Compliance Checks - DataCatalogStack", () => {
  let app: App;
  let stack: DataCatalogStack;

  beforeAll(() => {
    app = createTestApp();

    const deploymentConfig = createTestDeploymentConfig();
    const networkStack = new Stack(app, "NetworkStack", {
      env: createTestEnvironment()
    });
    const vpc = createTestVpc(networkStack);
    const selectedSubnets = vpc.selectSubnets({
      subnetType: SubnetType.PRIVATE_WITH_EGRESS
    });

    stack = new DataCatalogStack(app, "TestDataCatalogStack", {
      env: createTestEnvironment(),
      deployment: deploymentConfig,
      vpc: vpc,
      selectedSubnets: selectedSubnets
    });

    // Add the cdk-nag AwsSolutions Pack with extra verbose logging enabled.
    Aspects.of(stack).add(
      new AwsSolutionsChecks({
        verbose: true
      })
    );

    const errors = Annotations.fromStack(stack).findError(
      "*",
      Match.stringLikeRegexp("AwsSolutions-.*")
    );
    const warnings = Annotations.fromStack(stack).findWarning(
      "*",
      Match.stringLikeRegexp("AwsSolutions-.*")
    );
    generateNagReport(stack, errors, warnings);
  });

  test("No unsuppressed Warnings", () => {
    const warnings = Annotations.fromStack(stack).findWarning(
      "*",
      Match.stringLikeRegexp("AwsSolutions-.*")
    );
    expect(warnings).toHaveLength(0);
  });

  test("No unsuppressed Errors", () => {
    const errors = Annotations.fromStack(stack).findError(
      "*",
      Match.stringLikeRegexp("AwsSolutions-.*")
    );
    expect(errors).toHaveLength(0);
  });
});
