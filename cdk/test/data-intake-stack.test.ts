/*
 * Copyright 2025 Amazon.com, Inc. or its affiliates.
 */

/**
 * Unit tests for DataIntakeStack.
 */

import "source-map-support/register";

import { App, Aspects, Stack } from "aws-cdk-lib";
import { Annotations, Match, Template } from "aws-cdk-lib/assertions";
import { SynthesisMessage } from "aws-cdk-lib/cx-api";
import { AwsSolutionsChecks } from "cdk-nag";

import { DataIntakeConfig, DataIntakeStack } from "../lib/data-intake-stack";
import {
  createTestAccount,
  createTestApp,
  createTestVpc,
  generateNagReport
} from "./test-utils";

describe("DataIntakeStack", () => {
  let app: App;
  let account: ReturnType<typeof createTestAccount>;

  beforeEach(() => {
    app = createTestApp();
    account = createTestAccount();
  });

  test("creates stack with correct properties", () => {
    const networkStack = new Stack(app, "NetworkStack");
    const vpc = createTestVpc(networkStack);

    const stack = new DataIntakeStack(app, "TestDataIntakeStack", {
      account: account,
      vpc: vpc,
      config: new DataIntakeConfig({
        BUILD_FROM_SOURCE: false // Avoid slow container builds in tests
      }),
      env: {
        account: account.id,
        region: account.region
      }
    });

    // Stack should exist and have correct termination protection
    expect(stack.terminationProtection).toBe(false);

    // Dataplane should be created
    expect(stack.dataIntakeDataplane).toBeDefined();
  });

  test("sets termination protection when prodLike is true", () => {
    const prodAccount = createTestAccount({ prodLike: true });

    const networkStack = new Stack(app, "NetworkStack");
    const vpc = createTestVpc(networkStack);

    const stack = new DataIntakeStack(app, "TestDataIntakeStack", {
      account: prodAccount,
      vpc: vpc,
      config: new DataIntakeConfig({
        BUILD_FROM_SOURCE: false // Avoid slow container builds in tests
      }),
      env: {
        account: prodAccount.id,
        region: prodAccount.region
      },
      terminationProtection: prodAccount.prodLike
    });

    expect(stack.terminationProtection).toBe(true);
  });

  test("creates dataplane construct with resources", () => {
    const networkStack = new Stack(app, "NetworkStack");
    const vpc = createTestVpc(networkStack);

    const stack = new DataIntakeStack(app, "TestDataIntakeStack", {
      account: account,
      vpc: vpc,
      config: new DataIntakeConfig({
        BUILD_FROM_SOURCE: false // Avoid slow container builds in tests
      }),
      env: {
        account: account.id,
        region: account.region
      }
    });

    // Dataplane should be created
    expect(stack.dataIntakeDataplane).toBeDefined();

    const template = Template.fromStack(stack);

    // Check for key resources
    template.resourceCountIs("AWS::Lambda::Function", 1);
    template.resourceCountIs("AWS::SNS::Topic", 2);
    template.resourceCountIs("AWS::S3::Bucket", 1);
    template.resourceCountIs("AWS::IAM::Role", 1);
  });
});

/*
describe("cdk-nag Compliance Checks - DataIntakeStack", () => {
  let app: App;
  let stack: DataIntakeStack;

  beforeAll(() => {
    app = createTestApp();
    const account = createTestAccount();

    const networkStack = new Stack(app, "NetworkStack");
    const vpc = createTestVpc(networkStack);

    stack = new DataIntakeStack(app, "TestDataIntakeStack", {
      account: account,
      vpc: vpc,
      config: new DataIntakeConfig({
        BUILD_FROM_SOURCE: false // Avoid slow container builds in tests
      }),
      env: {
        account: account.id,
        region: account.region
      }
    });

    // Add the cdk-nag AwsSolutions Pack with extra verbose logging enabled.
    Aspects.of(stack).add(
      new AwsSolutionsChecks({
        verbose: true
      })
    );

    const errors: SynthesisMessage[] = Annotations.fromStack(stack).findError(
      "*",
      Match.stringLikeRegexp("AwsSolutions-.*")
    );
    const warnings: SynthesisMessage[] = Annotations.fromStack(stack).findWarning(
      "*",
      Match.stringLikeRegexp("AwsSolutions-.*")
    );
    generateNagReport(stack, errors, warnings);
  });

  test("No unsuppressed Warnings", () => {
    const warnings: SynthesisMessage[] = Annotations.fromStack(stack).findWarning(
      "*",
      Match.stringLikeRegexp("AwsSolutions-.*")
    );
    expect(warnings).toHaveLength(0);
  });

  test("No unsuppressed Errors", () => {
    const errors: SynthesisMessage[] = Annotations.fromStack(stack).findError(
      "*",
      Match.stringLikeRegexp("AwsSolutions-.*")
    );
    expect(errors).toHaveLength(0);
  });
});
*/
