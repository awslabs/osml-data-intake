/*
 * Copyright 2023-2025 Amazon.com, Inc. or its affiliates.
 */

import { Runtime } from "aws-cdk-lib/aws-lambda";

/**
 * OSML Account configuration interface.
 */
export interface OSMLAccount {
  /** The AWS account ID. */
  readonly id: string;
  /** The AWS region. */
  readonly region: string;
  /** Whether this is a production-like environment. Defaults to false if not specified. */
  readonly prodLike?: boolean;
  /** Whether this is an ADC (Application Data Center) environment. Defaults to false if not specified. */
  readonly isAdc?: boolean;
}

/**
 * Regional configuration interface.
 */
export interface RegionalConfigData {
  /** The S3 endpoint for the region. */
  readonly s3Endpoint: string;
  /** The maximum number of availability zones. */
  readonly maxVpcAzs: number;
  /** The runtime environment for deploying ECR CDK. */
  readonly ecrCdkDeployRuntime: Runtime;
  /** The instance type for the SageMaker GPU endpoint. */
  readonly sageMakerGpuEndpointInstanceType: string;
}

/**
 * Base configuration type for OSML constructs.
 */
export type ConfigType = Record<string, unknown>;

/**
 * Base configuration class for OSML constructs.
 *
 * This class provides a common implementation for initializing configuration objects
 * from a provided configuration object. It uses the `Object.assign` method to copy
 * properties from the provided configuration object to the instance, allowing for
 * easy extension by specific configuration classes.
 *
 * @example
 * // Define a specific configuration class by extending BaseConfig
 * class MyConfig extends BaseConfig {
 *   public someProperty: string;
 *   public anotherProperty: number;
 *
 *   constructor(config: ConfigType = {}) {
 *     super(config);
 *     this.someProperty = this.someProperty ?? "default value";
 *     this.anotherProperty = this.anotherProperty ?? 42;
 *   }
 * }
 *
 * // Create an instance of the specific configuration class
 * const config = new MyConfig({ someProperty: "custom value" });
 * console.log(config.someProperty); // Output: "custom value"
 * console.log(config.anotherProperty); // Output: 42
 */
export abstract class BaseConfig {
  /**
   * Constructor for BaseConfig.
   *
   * @param config - The configuration object
   */
  constructor(config: Partial<ConfigType> = {}) {
    Object.assign(this, config);
  }
}

/**
 * Regional configuration for AWS services.
 */
export class RegionalConfig {
  private static readonly configs: Record<string, RegionalConfigData> = {
    "us-east-1": {
      s3Endpoint: "s3.amazonaws.com",
      maxVpcAzs: 3,
      ecrCdkDeployRuntime: Runtime.PROVIDED_AL2023,
      sageMakerGpuEndpointInstanceType: "ml.p3.2xlarge"
    },
    "us-west-2": {
      s3Endpoint: "s3.us-west-2.amazonaws.com",
      maxVpcAzs: 3,
      ecrCdkDeployRuntime: Runtime.PROVIDED_AL2023,
      sageMakerGpuEndpointInstanceType: "ml.p3.2xlarge"
    },
    "us-west-1": {
      s3Endpoint: "s3.us-west-1.amazonaws.com",
      maxVpcAzs: 2,
      ecrCdkDeployRuntime: Runtime.PROVIDED_AL2023,
      sageMakerGpuEndpointInstanceType: "ml.g4dn.2xlarge"
    },
    "eu-west-1": {
      s3Endpoint: "s3.eu-west-1.amazonaws.com",
      maxVpcAzs: 3,
      ecrCdkDeployRuntime: Runtime.PROVIDED_AL2023,
      sageMakerGpuEndpointInstanceType: "ml.p3.2xlarge"
    },
    "ap-southeast-1": {
      s3Endpoint: "s3.ap-southeast-1.amazonaws.com",
      maxVpcAzs: 3,
      ecrCdkDeployRuntime: Runtime.PROVIDED_AL2023,
      sageMakerGpuEndpointInstanceType: "ml.p3.2xlarge"
    },
    "us-gov-west-1": {
      s3Endpoint: "s3.us-gov-west-1.amazonaws.com",
      maxVpcAzs: 2,
      ecrCdkDeployRuntime: Runtime.PROVIDED_AL2,
      sageMakerGpuEndpointInstanceType: "ml.p3.2xlarge"
    },
    "us-gov-east-1": {
      s3Endpoint: "s3.us-gov-east-1.amazonaws.com",
      maxVpcAzs: 2,
      ecrCdkDeployRuntime: Runtime.PROVIDED_AL2,
      sageMakerGpuEndpointInstanceType: "ml.g4dn.2xlarge"
    },
    "us-isob-east-1": {
      s3Endpoint: "s3.us-isob-east-1.sc2s.sgov.gov",
      maxVpcAzs: 2,
      ecrCdkDeployRuntime: Runtime.PROVIDED_AL2,
      sageMakerGpuEndpointInstanceType: "ml.p3.2xlarge"
    },
    "us-iso-east-1": {
      s3Endpoint: "s3.us-iso-east-1.c2s.ic.gov",
      maxVpcAzs: 2,
      ecrCdkDeployRuntime: Runtime.PROVIDED_AL2,
      sageMakerGpuEndpointInstanceType: "ml.p3.2xlarge"
    }
  };

  /**
   * Get regional configuration for a given region.
   *
   * @param region - The AWS region
   * @returns The regional configuration
   */
  static getConfig(region: string): RegionalConfigData {
    return this.configs[region] || this.configs["us-east-1"];
  }
}
