/*
 * Copyright 2025 Amazon.com, Inc. or its affiliates.
 */

/**
 * Unit tests for load-deployment functionality.
 */

import "source-map-support/register";

import { existsSync, unlinkSync, writeFileSync } from "fs";
import { join } from "path";

import { loadDeploymentConfig } from "../bin/deployment/load-deployment";

describe("loadDeploymentConfig", () => {
  const deploymentPath = join(__dirname, "../bin/deployment/deployment.json");
  const backupPath = deploymentPath + ".backup";

  beforeEach(() => {
    // Backup existing deployment.json if it exists
    if (existsSync(deploymentPath)) {
      const fs = require("fs");
      fs.copyFileSync(deploymentPath, backupPath);
    }
  });

  afterEach(() => {
    // Restore backup if it exists
    if (existsSync(backupPath)) {
      const fs = require("fs");
      fs.copyFileSync(backupPath, deploymentPath);
      unlinkSync(backupPath);
    } else if (existsSync(deploymentPath)) {
      // Remove test file if no backup existed
      unlinkSync(deploymentPath);
    }
  });

  test("loads valid deployment configuration", () => {
    const validConfig = {
      projectName: "TestProject",
      account: {
        id: "123456789012",
        region: "us-west-2",
        prodLike: false,
        isAdc: false
      },
      networkConfig: {
        VPC_NAME: "test-vpc"
      },
      dataplaneConfig: {
        BUILD_FROM_SOURCE: false
      }
    };

    writeFileSync(deploymentPath, JSON.stringify(validConfig, null, 2));

    const result = loadDeploymentConfig();

    expect(result.projectName).toBe("TestProject");
    expect(result.account.id).toBe("123456789012");
    expect(result.account.region).toBe("us-west-2");
    expect(result.account.prodLike).toBe(false);
    expect(result.account.isAdc).toBe(false);
    expect(result.networkConfig).toBeDefined();
    expect(result.dataplaneConfig).toBeDefined();
  });

  test("throws error for missing deployment.json", () => {
    if (existsSync(deploymentPath)) {
      unlinkSync(deploymentPath);
    }

    expect(() => loadDeploymentConfig()).toThrow(/Missing deployment.json/);
  });

  test("throws error for invalid JSON", () => {
    writeFileSync(deploymentPath, "{ invalid json }");

    expect(() => loadDeploymentConfig()).toThrow(/Invalid JSON format/);
  });

  test("throws error for missing projectName", () => {
    const invalidConfig = {
      account: {
        id: "123456789012",
        region: "us-west-2",
        prodLike: false
      }
    };

    writeFileSync(deploymentPath, JSON.stringify(invalidConfig, null, 2));

    expect(() => loadDeploymentConfig()).toThrow(
      /Missing required field: projectName/
    );
  });

  test("throws error for missing account", () => {
    const invalidConfig = {
      projectName: "TestProject"
    };

    writeFileSync(deploymentPath, JSON.stringify(invalidConfig, null, 2));

    expect(() => loadDeploymentConfig()).toThrow(
      /Missing or invalid account section/
    );
  });

  test("throws error for invalid account ID", () => {
    const invalidConfig = {
      projectName: "TestProject",
      account: {
        id: "invalid-id",
        region: "us-west-2",
        prodLike: false
      }
    };

    writeFileSync(deploymentPath, JSON.stringify(invalidConfig, null, 2));

    expect(() => loadDeploymentConfig()).toThrow(
      /Invalid AWS account ID format/
    );
  });

  test("throws error for invalid region", () => {
    const invalidConfig = {
      projectName: "TestProject",
      account: {
        id: "123456789012",
        region: "invalid-region",
        prodLike: false
      }
    };

    writeFileSync(deploymentPath, JSON.stringify(invalidConfig, null, 2));

    expect(() => loadDeploymentConfig()).toThrow(/Invalid AWS region format/);
  });

  test("handles optional configurations", () => {
    const minimalConfig = {
      projectName: "TestProject",
      account: {
        id: "123456789012",
        region: "us-west-2",
        prodLike: false
      }
    };

    writeFileSync(deploymentPath, JSON.stringify(minimalConfig, null, 2));

    const result = loadDeploymentConfig();

    expect(result.projectName).toBe("TestProject");
    expect(result.account.id).toBe("123456789012");
    expect(result.networkConfig).toBeUndefined();
    expect(result.dataplaneConfig).toBeUndefined();
    expect(result.dataCatalogConfig).toBeUndefined();
  });
});
