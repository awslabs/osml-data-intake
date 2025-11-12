/*
 * Copyright 2023-2025 Amazon.com, Inc. or its affiliates.
 */

import { App } from "aws-cdk-lib";
import { Template } from "aws-cdk-lib/assertions";

import { Account } from "../lib/constructs/shared/osml-account";

/**
 * Test utility functions for OSML Data Intake CDK tests.
 */

/**
 * Creates a test OSML account configuration.
 */
export function createTestAccount(): Account {
  return {
    id: "123456789012",
    region: "us-west-2",
    prodLike: false,
    isAdc: false
  };
}

/**
 * Creates a test CDK app.
 */
export function createTestApp(): App {
  return new App();
}

/**
 * Creates a CDK template from a stack for assertions.
 */
export function getTemplate(stack: any): Template {
  return Template.fromStack(stack);
}
