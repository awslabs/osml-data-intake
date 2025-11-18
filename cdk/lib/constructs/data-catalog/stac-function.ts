/*
 * Copyright 2024-2025 Amazon.com, Inc. or its affiliates.
 */

import { Duration, Size } from "aws-cdk-lib";
import { IVpc, Port, SubnetSelection } from "aws-cdk-lib/aws-ec2";
import { Effect, IRole, Policy, PolicyStatement } from "aws-cdk-lib/aws-iam";
import {
  DockerImageFunction,
  Function,
  LoggingFormat
} from "aws-cdk-lib/aws-lambda";
import { Domain } from "aws-cdk-lib/aws-opensearchservice";
import { NagSuppressions } from "cdk-nag";
import { Construct } from "constructs";

import { OSMLAccount } from "../types";
import { Container } from "./container";
import { DCDataplaneConfig } from "./dataplane";

/**
 * Properties for creating the STAC Lambda function.
 */
export interface StacFunctionProps {
  /** The OSML account configuration. */
  readonly account: OSMLAccount;
  /** The VPC configuration. */
  readonly vpc: IVpc;
  /** The selected subnets for the VPC. */
  readonly selectedSubnets: SubnetSelection;
  /** The IAM role for the Lambda function. */
  readonly lambdaRole: IRole;
  /** The STAC container. */
  readonly stacContainer: Container;
  /** The OpenSearch domain. */
  readonly osDomain: Domain;
  /** The DC dataplane configuration. */
  readonly config: DCDataplaneConfig;
}

/**
 * Construct that manages the STAC API Lambda function for the Data Catalog.
 *
 * This construct encapsulates the creation and configuration of the Lambda
 * function for the STAC API.
 */
export class StacFunction extends Construct {
  /** The Lambda function for the STAC API. */
  public readonly function: Function;

  /**
   * Creates a new StacFunction construct.
   *
   * @param scope - The scope/stack in which to define this construct
   * @param id - The id of this construct within the current scope
   * @param props - The properties for configuring this construct
   */
  constructor(scope: Construct, id: string, props: StacFunctionProps) {
    super(scope, id);

    // Create an operating ENV for our lambda container
    const env = {
      STAC_FASTAPI_TITLE: props.config.STAC_FASTAPI_TITLE,
      STAC_FASTAPI_DESCRIPTION: props.config.STAC_FASTAPI_DESCRIPTION,
      STAC_FASTAPI_VERSION: props.config.STAC_FASTAPI_VERSION,
      RELOAD: props.config.STAC_RELOAD,
      ENVIRONMENT: props.config.STAC_ENVIRONMENT,
      WEB_CONCURRENCY: props.config.STAC_WEB_CONCURRENCY,
      ES_HOST: props.osDomain.domainEndpoint,
      ES_PORT: props.config.STAC_ES_PORT,
      ES_USE_SSL: props.config.STAC_ES_USE_SSL,
      ES_VERIFY_CERTS: props.config.STAC_ES_VERIFY_CERTS,
      STAC_FASTAPI_ROOT_PATH: `/${props.config.STAC_FASTAPI_ROOT_PATH}`
    };

    // Create the STAC API Lambda function
    this.function = new DockerImageFunction(this, "DCStacFunction", {
      functionName: "DCStacLambda",
      code: props.stacContainer.dockerImageCode,
      role: props.lambdaRole,
      vpc: props.vpc,
      vpcSubnets: props.selectedSubnets,
      timeout: Duration.seconds(props.config.LAMBDA_TIMEOUT),
      ephemeralStorageSize: Size.gibibytes(props.config.LAMBDA_STORAGE_SIZE),
      memorySize: props.config.LAMBDA_MEMORY_SIZE,
      environment: env,
      loggingFormat: LoggingFormat.JSON
    });
    this.function.node.addDependency(props.stacContainer);

    // Allow the STAC Lambda to connect to OpenSearch
    props.osDomain.connections.allowFrom(this.function, Port.tcp(443));

    // Grant OpenSearch permissions to the Lambda role
    // This is required for the Lambda to query OpenSearch via IAM authentication
    const openSearchPolicy = new Policy(this, "StacOpenSearchPolicy", {
      statements: [
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: ["es:ESHttp*"],
          resources: [`${props.osDomain.domainArn}/*`]
        })
      ],
      roles: [props.lambdaRole]
    });

    // Note: Suppressing IAM5 without appliesTo because the domain ARN is a token
    // and cannot be matched exactly. This policy only contains OpenSearch wildcard
    // permissions scoped to the specific domain, which is acceptable.
    NagSuppressions.addResourceSuppressions(
      openSearchPolicy,
      [
        {
          id: "AwsSolutions-IAM5",
          reason:
            "Wildcard permissions on OpenSearch domain are required as the STAC API Lambda needs to perform various operations (GET, POST, PUT, DELETE) on different indices and paths within the domain. The permissions are scoped to the specific OpenSearch domain ARN. Action wildcard (es:ESHttp*) is needed for all HTTP methods, and resource wildcard (*) is needed for all indices and paths within the domain."
        }
      ],
      true
    );
  }
}
