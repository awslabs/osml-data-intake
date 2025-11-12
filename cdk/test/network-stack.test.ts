/*
 * Copyright 2025 Amazon.com, Inc. or its affiliates.
 */

/**
 * Unit tests for NetworkStack.
 */

import "source-map-support/register";

import { App, Aspects } from "aws-cdk-lib";
import { Annotations, Match, Template } from "aws-cdk-lib/assertions";
import { SynthesisMessage } from "aws-cdk-lib/cx-api";
import { AwsSolutionsChecks } from "cdk-nag";

import { NetworkStack } from "../lib/network-stack";
import {
  createTestAccount,
  createTestApp,
  generateNagReport
} from "./test-utils";

describe("NetworkStack", () => {
  let app: App;
  let account: ReturnType<typeof createTestAccount>;

  beforeEach(() => {
    app = createTestApp();
    account = createTestAccount();
  });

  test("creates stack with correct properties", () => {
    const stack = new NetworkStack(app, "TestNetworkStack", {
      account: account,
      env: {
        account: account.id,
        region: account.region
      }
    });

    // Stack should exist and have correct termination protection
    expect(stack.terminationProtection).toBe(false);

    // VPC should be created
    expect(stack.vpc).toBeDefined();
  });

  test("sets termination protection when prodLike is true", () => {
    const prodAccount = createTestAccount({ prodLike: true });

    const stack = new NetworkStack(app, "TestNetworkStack", {
      account: prodAccount,
      env: {
        account: prodAccount.id,
        region: prodAccount.region
      },
      terminationProtection: prodAccount.prodLike
    });

    expect(stack.terminationProtection).toBe(true);
  });

  test("creates VPC with default configuration", () => {
    const stack = new NetworkStack(app, "TestNetworkStack", {
      account: account,
      env: {
        account: account.id,
        region: account.region
      }
    });

    const template = Template.fromStack(stack);

    // Check for VPC resources
    template.resourceCountIs("AWS::EC2::VPC", 1);
    template.resourceCountIs("AWS::EC2::Subnet", 6); // 3 public + 3 private
    template.resourceCountIs("AWS::EC2::InternetGateway", 1);
    template.resourceCountIs("AWS::EC2::NatGateway", 3);
  });

  test("creates VPC with custom name", () => {
    const customConfig = {
      VPC_NAME: "custom-vpc-name"
    };

    const stack = new NetworkStack(app, "TestNetworkStack", {
      account: account,
      config: customConfig,
      env: {
        account: account.id,
        region: account.region
      }
    });

    const template = Template.fromStack(stack);

    // VPC should have custom name
    template.hasResourceProperties("AWS::EC2::VPC", {
      Tags: Match.arrayWith([
        {
          Key: "Name",
          Value: "custom-vpc-name"
        }
      ])
    });
  });
});
/*
describe("cdk-nag Compliance Checks - NetworkStack", () => {
  let app: App;
  let stack: NetworkStack;

  beforeAll(() => {
    app = createTestApp();
    const account = createTestAccount();

    stack = new NetworkStack(app, "TestNetworkStack", {
      account: account,
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
