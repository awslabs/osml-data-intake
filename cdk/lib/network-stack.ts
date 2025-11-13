/*
 * Copyright 2023-2025 Amazon.com, Inc. or its affiliates.
 */

import { Stack, StackProps } from "aws-cdk-lib";
import { Construct } from "constructs";

import { OSMLVpc } from "./constructs/shared/osml-vpc";
import { BaseConfig, OSMLAccount } from "./constructs/types";

/**
 * Configuration class for NetworkStack.
 */
export class NetworkConfig extends BaseConfig {
  /**
   * The name of the VPC to be created.
   * @default "data-intake-vpc"
   */
  public VPC_NAME: string;

  /**
   * Creates an instance of NetworkConfig.
   * @param {object} config - The configuration object.
   */
  constructor(config: object = {}) {
    super({
      VPC_NAME: "data-intake-vpc",
      ...config
    });
  }
}

/**
 * Interface representing the properties for configuring the Network Stack.
 */
export interface NetworkStackProps extends StackProps {
  /**
   * The deployment account.
   * @type {OSMLAccount}
   */
  account: OSMLAccount;

  /**
   * Custom configuration for the NetworkStack.
   * @type {NetworkConfig | undefined}
   */
  config?: NetworkConfig;
}

/**
 * This stack provisions all of the foundational networking configuration.
 * It sets up an Amazon VPC (Virtual Private Cloud) along with public and private subnets
 * across multiple availability zones to ensure high availability. The stack also creates
 * essential VPC endpoints for secure communication with AWS services without internet access
 * and configures VPC Flow Logs for network monitoring and security analysis.
 * All of these networking components are designed to provide a secure, isolated,
 * and well-monitored network environment for workloads.
 */
export class NetworkStack extends Stack {
  /**
   * The configuration for the network stack.
   */
  public config: NetworkConfig;

  /**
   * The VPC construct.
   */
  public vpc: OSMLVpc;

  /**
   * Creates an instance of NetworkStack.
   * @param {Construct} scope - The scope/stack in which to define this construct.
   * @param {string} id - The id of this construct within the current scope.
   * @param {NetworkStackProps} props - The properties of this construct.
   */
  constructor(scope: Construct, id: string, props: NetworkStackProps) {
    super(scope, id, props);

    // Check if a custom configuration was provided or create a default one
    this.config = props.config ?? new NetworkConfig();

    // Create the VPC with all the networking resources
    this.vpc = new OSMLVpc(this, "Vpc", {
      account: props.account,
      config: {
        VPC_NAME: this.config.VPC_NAME
      }
    });
  }
}
