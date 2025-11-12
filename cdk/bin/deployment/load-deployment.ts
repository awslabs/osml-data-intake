/**
 * Copyright 2023-2025 Amazon.com, Inc. or its affiliates.
 */

/**
 * Utility to load and validate the deployment configuration file for OSML Data Intake.
 *
 * This module provides a strongly typed interface for reading the `deployment.json`
 * configuration, performing required validations, and returning a structured result
 * specifically tailored for data intake deployments.
 *
 * Expected structure of `deployment.json`:
 * ```json
 * {
 *   "projectName": "osml-data-intake",
 *   "account": {
 *     "id": "123456789012",
 *     "region": "us-west-2",
 *     "prodLike": false
 *   },
 *   "networkConfig": {
 *     "VPC_NAME": "osml-vpc"
 *   },
 *   "dataIntakeConfig": {
 *     "BUILD_FROM_SOURCE": false,
 *     "CONTAINER_URI": "awsosml/osml-data-intake-intake:latest"
 *   }
 * }
 * ```
 *
 * @packageDocumentation
 */

import { existsSync, readFileSync } from "fs";
import { join } from "path";

import { Account } from "../../lib/constructs/shared/osml-account";
import { DataCatalogConfig } from "../../lib/data-catalog-stack";
import { DataIntakeConfig } from "../../lib/data-intake-stack";
import { NetworkConfig } from "../../lib/network-stack";

/**
 * Represents the deployment configuration specific to data intake.
 */
export interface DeploymentConfig {
  /** The project name. */
  projectName: string;
  /** The deployment account. */
  account: Account;
  /** Network configuration for the deployment. */
  networkConfig?: NetworkConfig;
  /** Data intake specific configuration. */
  dataplaneConfig?: DataIntakeConfig;
  /** Data catalog specific configuration. */
  dataCatalogConfig?: DataCatalogConfig;
}

/**
 * Validation error class for deployment configuration issues.
 */
class DeploymentConfigError extends Error {
  constructor(
    message: string,
    public field?: string
  ) {
    super(message);
    this.name = "DeploymentConfigError";
  }
}

/**
 * Validates and trims a string field.
 */
function validateStringField(
  value: unknown,
  fieldName: string,
  isRequired: boolean = true
): string {
  if (value === undefined || value === null) {
    if (isRequired) {
      throw new DeploymentConfigError(
        `Missing required field: ${fieldName}`,
        fieldName
      );
    }
    return "";
  }

  if (typeof value !== "string") {
    throw new DeploymentConfigError(
      `Field '${fieldName}' must be a string, got ${typeof value}`,
      fieldName
    );
  }

  const trimmed = value.trim();
  if (isRequired && trimmed === "") {
    throw new DeploymentConfigError(
      `Field '${fieldName}' cannot be empty or contain only whitespace`,
      fieldName
    );
  }

  return trimmed;
}

/**
 * Validates AWS account ID format.
 */
function validateAccountId(accountId: string): string {
  if (!/^\d{12}$/.test(accountId)) {
    throw new DeploymentConfigError(
      `Invalid AWS account ID format: '${accountId}'. Must be exactly 12 digits.`,
      "account.id"
    );
  }
  return accountId;
}

/**
 * Validates AWS region format.
 */
function validateRegion(region: string): string {
  // AWS regions follow strict pattern: 2-3 letter geo code, dash, direction, dash, number
  // Examples: us-east-1, eu-west-2, ap-southeast-1, ca-central-1, me-south-1
  if (
    !/^(us|eu|ap|ca|sa|af|me|il|cn|gov)-(east|west|north|south|central|southeast|northeast|southwest|northwest)-[1-9]\d*$/.test(
      region
    )
  ) {
    throw new DeploymentConfigError(
      `Invalid AWS region format: '${region}'. Must follow AWS region pattern like 'us-east-1', 'eu-west-2', etc.`,
      "account.region"
    );
  }
  return region;
}

/**
 * Loads and validates the deployment configuration from `deployment/deployment.json`.
 */
export function loadDeploymentConfig(): DeploymentConfig {
  const deploymentPath = join(__dirname, "deployment.json");

  if (!existsSync(deploymentPath)) {
    throw new DeploymentConfigError(
      `Missing deployment.json file at ${deploymentPath}. Please create it by copying deployment.json.example`
    );
  }

  let parsed: unknown;
  try {
    const rawContent = readFileSync(deploymentPath, "utf-8");
    parsed = JSON.parse(rawContent) as unknown;
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new DeploymentConfigError(
        `Invalid JSON format in deployment.json: ${error.message}`
      );
    }
    throw new DeploymentConfigError(
      `Failed to read deployment.json: ${error instanceof Error ? error.message : "Unknown error"}`
    );
  }

  if (!parsed || typeof parsed !== "object" || parsed === null) {
    throw new DeploymentConfigError(
      "deployment.json must contain a valid JSON object"
    );
  }

  const parsedObj = parsed as Record<string, unknown>;

  // Validate account section
  if (!parsedObj.account || typeof parsedObj.account !== "object") {
    throw new DeploymentConfigError(
      "Missing or invalid account section in deployment.json",
      "account"
    );
  }

  const accountObj = parsedObj.account as Record<string, unknown>;
  const accountId = validateAccountId(
    validateStringField(accountObj.id, "account.id")
  );
  const region = validateRegion(
    validateStringField(accountObj.region, "account.region")
  );
  const prodLike = (accountObj.prodLike as boolean | undefined) ?? false;

  // Validate project name
  const projectName = validateStringField(parsedObj.projectName, "projectName");

  // Handle isAdc field
  const isAdc = (accountObj.isAdc as boolean | undefined) ?? false;

  // Create Account object
  const account: Account = {
    id: accountId,
    region: region,
    prodLike: prodLike,
    isAdc: isAdc
  };

  // Parse optional network configuration
  let networkConfig: NetworkConfig | undefined = undefined;
  if (
    parsedObj.networkConfig &&
    typeof parsedObj.networkConfig === "object" &&
    parsedObj.networkConfig !== null
  ) {
    networkConfig = new NetworkConfig(
      parsedObj.networkConfig as Record<string, unknown>
    );
  }

  // Parse optional dataplane configuration
  let dataplaneConfig: DataIntakeConfig | undefined = undefined;
  if (
    parsedObj.dataplaneConfig &&
    typeof parsedObj.dataplaneConfig === "object" &&
    parsedObj.dataplaneConfig !== null
  ) {
    dataplaneConfig = new DataIntakeConfig(
      parsedObj.dataplaneConfig as Record<string, unknown>
    );
  }

  // Parse optional data catalog configuration
  let dataCatalogConfig: DataCatalogConfig | undefined = undefined;
  if (
    parsedObj.dataCatalogConfig &&
    typeof parsedObj.dataCatalogConfig === "object" &&
    parsedObj.dataCatalogConfig !== null
  ) {
    dataCatalogConfig = new DataCatalogConfig(
      parsedObj.dataCatalogConfig as Record<string, unknown>
    );
  }

  // Log configuration (only once to prevent duplicate logging)
  const globalObj = global as { __dataIntakeDeploymentConfigLoaded?: boolean };
  if (!globalObj.__dataIntakeDeploymentConfigLoaded) {
    console.log(
      `🚀 Loading OSML Data Intake deployment configuration: region=${account.region}, prodLike=${account.prodLike}`
    );
    globalObj.__dataIntakeDeploymentConfigLoaded = true;
  }

  return {
    projectName,
    account,
    networkConfig,
    dataplaneConfig,
    dataCatalogConfig
  };
}

/**
 * Convenience function that matches the expected interface from the main app.
 */
export function loadDeployment(): DeploymentConfig {
  return loadDeploymentConfig();
}
