/*
 * Copyright 2023-2025 Amazon.com, Inc. or its affiliates.
 */

import { Stack, StackProps } from "aws-cdk-lib";
import { Construct } from "constructs";

import { DIDataplane } from "./constructs/data-intake/di-dataplane";
import { Account } from "./constructs/shared/osml-account";
import { OSMLVpc } from "./constructs/shared/osml-vpc";
import { BaseConfig } from "./constructs/shared/utils/base-config";

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
   * @type {Account}
   */
  account: Account;

  /**
   * The VPC (Virtual Private Cloud) configuration for the stack.
   * @type {OSMLVpc}
   */
  vpc: OSMLVpc;

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
  public dataIntakeDataplane: DIDataplane;

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

    // Create the data intake dataplane with all required resources
    this.dataIntakeDataplane = new DIDataplane(this, "DIDataplane", {
      account: props.account,
      vpc: props.vpc
    });
  }
}
