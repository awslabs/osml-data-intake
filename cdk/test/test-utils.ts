/*
 * Copyright 2023-2025 Amazon.com, Inc. or its affiliates.
 */

import { App, Environment, Stack } from "aws-cdk-lib";
import { Template } from "aws-cdk-lib/assertions";
import { SynthesisMessage } from "aws-cdk-lib/cx-api";

import { OSMLVpc } from "../lib/constructs/shared/osml-vpc";
import { OSMLAccount } from "../lib/constructs/types";

/**
 * Test utility functions for Data Intake CDK tests.
 */

/**
 * Creates a test account configuration.
 */
export function createTestAccount(
  overrides: Partial<OSMLAccount> = {}
): OSMLAccount {
  return {
    id: "123456789012",
    region: "us-west-2",
    prodLike: false,
    isAdc: false,
    ...overrides
  };
}

/**
 * Creates a test CDK app.
 */
export function createTestApp(): App {
  return new App();
}

/**
 * Creates a test environment configuration.
 */
export function createTestEnvironment(): Environment {
  return {
    account: "123456789012",
    region: "us-west-2"
  };
}

/**
 * Creates a test VPC for testing.
 */
export function createTestVpc(scope: Stack): OSMLVpc {
  const account = createTestAccount();
  return new OSMLVpc(scope, "TestVpc", {
    account: account
  });
}

/**
 * Creates a CDK template from a stack for assertions.
 */
export function getTemplate(stack: any): Template {
  return Template.fromStack(stack);
}

/**
 * Generates a simple cdk-nag report for testing.
 */
export function generateNagReport(
  stack: Stack,
  errors: SynthesisMessage[],
  warnings: SynthesisMessage[]
): void {
  if (errors.length > 0 || warnings.length > 0) {
    console.log(`\n=== CDK-NAG Report for ${stack.stackName} ===`);

    if (errors.length > 0) {
      console.log(`\nErrors (${errors.length}):`);
      errors.forEach((error, index) => {
        const data =
          typeof error.entry.data === "string"
            ? error.entry.data
            : JSON.stringify(error.entry.data);
        console.log(`${index + 1}. ${data}`);
      });
    }

    if (warnings.length > 0) {
      console.log(`\nWarnings (${warnings.length}):`);
      warnings.forEach((warning, index) => {
        const data =
          typeof warning.entry.data === "string"
            ? warning.entry.data
            : JSON.stringify(warning.entry.data);
        console.log(`${index + 1}. ${data}`);
      });
    }

    console.log(`\n=== End CDK-NAG Report ===\n`);
  }
}
