/*
 * Copyright 2023-2025 Amazon.com, Inc. or its affiliates.
 */

import { Stack, StackProps } from "aws-cdk-lib";
import { Construct } from "constructs";

import { DIDataplane } from "./constructs/data-intake/di-dataplane";
import { OSMLVpc } from "./constructs/shared/osml-vpc";
import { BaseConfig, OSMLAccount } from "./constructs/types";

/**
 * Configuration class for DataIntakeStack.
 */
export class DataIntakeConfig extends BaseConfig {
  /**
   * Creates an instance of DataIntakeConfig.
   * @param {object} config - The configuration object.
   */
  constructor(config: object = {}) {
    super({
      ...config
    });
  }
}

/**
 * Interface representing the properties for configuring the Data Intake Stack.
 */
export interface DataIntakeStackProps extends StackProps {
  /**
   * The deployment account.
   * @type {OSMLAccount}
   */
  account: OSMLAccount;

  /**
   * The VPC (Virtual Private Cloud) configuration for the stack.
   * @type {OSMLVpc}
   */
  vpc: OSMLVpc | null;

  /**
   * Custom configuration for the DataIntakeStack.
   * @type {DataIntakeConfig | undefined}
   */
  config?: DataIntakeConfig;
}

/**
 * This stack provisions all of the resources required to run the Data Intake service.
 * It includes Lambda functions for processing incoming data, SNS topics for event-driven
 * processing, S3 buckets for data storage, and associated IAM roles and policies.
 * The stack integrates with the provided VPC for secure network communication and
 * follows security and operational best practices.
 */
export class DataIntakeStack extends Stack {
  /**
   * The configuration for the data intake stack.
   */
  public config: DataIntakeConfig;

  /**
   * The data intake dataplane construct containing all processing resources.
   */
  public dataIntakeDataplane?: DIDataplane;

  /**
   * Creates an instance of DataIntakeStack.
   * @param {Construct} scope - The scope/stack in which to define this construct.
   * @param {string} id - The id of this construct within the current scope.
   * @param {DataIntakeStackProps} props - The properties of this construct.
   */
  constructor(scope: Construct, id: string, props: DataIntakeStackProps) {
    super(scope, id, props);

    // Check if a custom configuration was provided or create a default one
    this.config = props.config ?? new DataIntakeConfig();

    // Create the data intake dataplane with all required resources if VPC is provided
    if (props.vpc) {
      this.createDataplane(props.account, props.vpc);
    }
  }

  /**
   * Creates the data intake dataplane with the provided VPC.
   * @param account - The deployment account
   * @param vpc - The VPC configuration
   */
  public createDataplane(account: OSMLAccount, vpc: OSMLVpc): void {
    this.dataIntakeDataplane = new DIDataplane(this, "DIDataplane", {
      account: account,
      vpc: vpc
    });
  }

  /**
   * Sets the VPC for this stack and creates the dataplane if not already created.
   * @param account - The deployment account
   * @param vpc - The VPC configuration
   */
  public setVpc(account: OSMLAccount, vpc: OSMLVpc): void {
    if (!this.dataIntakeDataplane) {
      this.createDataplane(account, vpc);
    }
  }
}
