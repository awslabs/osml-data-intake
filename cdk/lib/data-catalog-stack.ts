/*
 * Copyright 2023-2025 Amazon.com, Inc. or its affiliates.
 */

import { Stack, StackProps } from "aws-cdk-lib";
import { Construct } from "constructs";

import { DCDataplane } from "./constructs/data-catalog/dc-dataplane";
import { OSMLVpc } from "./constructs/shared/osml-vpc";
import { BaseConfig, OSMLAccount } from "./constructs/types";

/**
 * Configuration class for DataCatalogStack.
 */
export class DataCatalogConfig extends BaseConfig {
  /**
   * Creates an instance of DataCatalogConfig.
   * @param {object} config - The configuration object.
   */
  constructor(config: object = {}) {
    super({
      ...config
    });
  }
}

/**
 * Interface representing the properties for configuring the Data Catalog Stack.
 */
export interface DataCatalogStackProps extends StackProps {
  /**
   * The deployment account.
   * @type {Account}
   */
  account: OSMLAccount;

  /**
   * The VPC (Virtual Private Cloud) configuration for the stack.
   * @type {OSMLVpc}
   */
  vpc: OSMLVpc;

  /**
   * Custom configuration for the DataCatalogStack.
   * @type {DataCatalogConfig | undefined}
   */
  config?: DataCatalogConfig;
}

/**
 * This stack provisions all of the resources required to run the Data Catalog service.
 * It includes OpenSearch domain, Lambda functions for STAC processing, SNS topics,
 * and associated IAM roles and policies for data cataloging and search capabilities.
 */
export class DataCatalogStack extends Stack {
  /**
   * The configuration for the data catalog stack.
   */
  public config: DataCatalogConfig;

  /**
   * The data catalog dataplane construct containing all processing resources.
   */
  public dataCatalogDataplane: DCDataplane;

  /**
   * Creates an instance of DataCatalogStack.
   * @param {Construct} scope - The scope/stack in which to define this construct.
   * @param {string} id - The id of this construct within the current scope.
   * @param {DataCatalogStackProps} props - The properties of this construct.
   */
  constructor(scope: Construct, id: string, props: DataCatalogStackProps) {
    super(scope, id, props);

    // Check if a custom configuration was provided or create a default one
    this.config = props.config ?? new DataCatalogConfig();

    // Create the data catalog dataplane with all required resources
    this.dataCatalogDataplane = new DCDataplane(this, "DCDataplane", {
      account: props.account,
      vpc: props.vpc
    });
  }
}
