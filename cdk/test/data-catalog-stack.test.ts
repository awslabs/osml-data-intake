/*
 * Copyright 2025 Amazon.com, Inc. or its affiliates.
 */

/**
 * Unit tests for DataCatalogStack.
 */

import "source-map-support/register";

import { App, Stack } from "aws-cdk-lib";
import { Template } from "aws-cdk-lib/assertions";

import { DataCatalogConfig, DataCatalogStack } from "../lib/data-catalog-stack";
import { createTestAccount, createTestApp, createTestVpc } from "./test-utils";

describe("DataCatalogStack", () => {
  let app: App;
  let stack: DataCatalogStack;
  let prodStack: DataCatalogStack;
  let template: Template;
  let account: ReturnType<typeof createTestAccount>;
  let prodAccount: ReturnType<typeof createTestAccount>;

  beforeAll(() => {
    // Create regular stack
    app = createTestApp();
    account = createTestAccount();

    const networkStack = new Stack(app, "NetworkStack", {
      env: {
        account: account.id,
        region: account.region
      }
    });
    const vpc = createTestVpc(networkStack);

    stack = new DataCatalogStack(app, "TestDataCatalogStack", {
      account: account,
      vpc: vpc,
      config: new DataCatalogConfig({
        BUILD_FROM_SOURCE: false
      }),
      env: {
        account: account.id,
        region: account.region
      }
    });

    template = Template.fromStack(stack);

    // Create prod stack for termination protection test
    const prodApp = createTestApp();
    prodAccount = createTestAccount({ prodLike: true });

    const prodNetworkStack = new Stack(prodApp, "ProdNetworkStack", {
      env: {
        account: prodAccount.id,
        region: prodAccount.region
      }
    });
    const prodVpc = createTestVpc(prodNetworkStack);

    prodStack = new DataCatalogStack(prodApp, "ProdDataCatalogStack", {
      account: prodAccount,
      vpc: prodVpc,
      config: new DataCatalogConfig({
        BUILD_FROM_SOURCE: false
      }),
      env: {
        account: prodAccount.id,
        region: prodAccount.region
      },
      terminationProtection: prodAccount.prodLike
    });
  });

  test("creates stack with correct properties", () => {
    expect(stack.terminationProtection).toBe(false);
    expect(stack.dataCatalogDataplane).toBeDefined();
  });

  test("sets termination protection when prodLike is true", () => {
    expect(prodStack.terminationProtection).toBe(true);
  });

  test("creates dataplane construct with resources", () => {
    expect(stack.dataCatalogDataplane).toBeDefined();

    // Check for key resources - update counts based on actual resources created
    template.resourceCountIs("AWS::Lambda::Function", 3); // STAC + Ingest + OpenSearch Access Policy Lambda
    template.resourceCountIs("AWS::OpenSearchService::Domain", 1);
    template.resourceCountIs("AWS::SNS::Topic", 1);

    // Check that our specific Lambda functions exist
    template.hasResourceProperties("AWS::Lambda::Function", {
      FunctionName: "DataCatalogStacFunction"
    });
    template.hasResourceProperties("AWS::Lambda::Function", {
      FunctionName: "DataCatalogIngestFunction"
    });
  });
});
/*
describe("cdk-nag Compliance Checks - DataCatalogStack", () => {
  let app: App;
  let stack: DataCatalogStack;

  beforeAll(() => {
    app = createTestApp();
    const account = createTestAccount();

    const networkStack = new Stack(app, "NetworkStack");
    const vpc = createTestVpc(networkStack);

    stack = new DataCatalogStack(app, "TestDataCatalogStack", {
      account: account,
      vpc: vpc,
      config: new DataCatalogConfig({
        BUILD_FROM_SOURCE: false
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
