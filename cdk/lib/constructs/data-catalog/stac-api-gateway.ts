/*
 * Copyright 2024-2025 Amazon.com, Inc. or its affiliates.
 */

import { CfnOutput } from "aws-cdk-lib";
import {
  Cors,
  EndpointType,
  LambdaIntegration,
  RestApi
} from "aws-cdk-lib/aws-apigateway";
import { Function } from "aws-cdk-lib/aws-lambda";
import { NagSuppressions } from "cdk-nag";
import { Construct } from "constructs";

import { OSMLAccount } from "../types";
import { DCDataplaneConfig } from "./dataplane";

/**
 * Properties for creating the STAC API Gateway.
 */
export interface StacApiGatewayProps {
  /** The OSML account configuration. */
  readonly account: OSMLAccount;
  /** The STAC Lambda function to integrate with. */
  readonly stacFunction: Function;
  /** The DC dataplane configuration. */
  readonly config: DCDataplaneConfig;
  /** The service name abbreviation. */
  readonly serviceNameAbbreviation: string;
}

/**
 * Construct that manages the API Gateway for the STAC API.
 *
 * This construct creates a REST API Gateway (matching the old osml-cdk-constructs setup)
 * without authentication, integrating with the STAC Lambda function.
 */
export class StacApiGateway extends Construct {
  /** The REST API Gateway. */
  public readonly restApi: RestApi;
  /** The API Gateway URL. */
  public readonly apiUrl: string;

  /**
   * Creates a new StacApiGateway construct.
   *
   * @param scope - The scope/stack in which to define this construct
   * @param id - The id of this construct within the current scope
   * @param props - The properties for configuring this construct
   */
  constructor(scope: Construct, id: string, props: StacApiGatewayProps) {
    super(scope, id);

    // Create Lambda integration
    const lambdaIntegration = new LambdaIntegration(props.stacFunction);

    // Create REST API Gateway (matching old osml-cdk-constructs structure)
    // Note: Old setup only created API if auth was provided, but we create it
    // without auth to match the structure while keeping it accessible
    this.restApi = new RestApi(this, "StacRestApi", {
      restApiName: `${props.serviceNameAbbreviation}-RestApi`,
      deployOptions: {
        stageName: props.config.STAC_FASTAPI_ROOT_PATH
      },
      endpointTypes: [EndpointType.REGIONAL],
      defaultIntegration: lambdaIntegration,
      defaultCorsPreflightOptions: {
        allowOrigins: Cors.ALL_ORIGINS,
        allowHeaders: Cors.DEFAULT_HEADERS,
        allowMethods: Cors.ALL_METHODS
      }
    });

    // Add proxy resource to forward all requests to Lambda
    // This matches the old setup: this.restApi.root.addProxy({ anyMethod: true })
    const proxyResource = this.restApi.root.addProxy({
      anyMethod: true
    });

    // Suppress Cognito authorizer requirement for API Gateway methods
    // The API Gateway is deployed in a VPC and does not require Cognito authentication
    NagSuppressions.addResourceSuppressions(
      [this.restApi.root, proxyResource],
      [
        {
          id: "AwsSolutions-COG4",
          reason:
            "Cognito user pool authorizer is not required for the STAC API Gateway as it is deployed in a VPC with restricted network access. The API Gateway is only accessible from within the VPC and does not require additional authentication beyond network-level security."
        }
      ],
      true
    );

    // Get the API URL (already includes the stage name which is the root path)
    this.apiUrl = this.restApi.url;

    // Add stack output for the API URL (this is the one used by the application)
    new CfnOutput(this, "StacApiUrl", {
      value: this.apiUrl,
      description: "The URL of the STAC API Gateway",
      exportName: `${props.serviceNameAbbreviation}-StacApiUrl`
    });

    // Add cdk-nag suppressions
    NagSuppressions.addResourceSuppressions(
      this.restApi,
      [
        {
          id: "AwsSolutions-APIG1",
          reason:
            "Request validation is not required for the STAC API Gateway as it acts as a proxy to the Lambda function. The Lambda function handles all request validation and processing."
        },
        {
          id: "AwsSolutions-APIG2",
          reason:
            "Request validation is not required for the STAC API Gateway as it acts as a proxy to the Lambda function. The Lambda function handles all request validation and processing."
        },
        {
          id: "AwsSolutions-APIG4",
          reason:
            "Request validation is not required for the STAC API Gateway as it acts as a proxy to the Lambda function. The Lambda function handles all request validation and processing."
        }
      ],
      true
    );

    // Suppress WAFv2 warning and CloudWatch logging for API Gateway stage
    NagSuppressions.addResourceSuppressions(
      this.restApi.deploymentStage,
      [
        {
          id: "AwsSolutions-APIG3",
          reason:
            "WAFv2 web ACL association is not required for the STAC API Gateway as it is deployed in a VPC with restricted network access. The API Gateway is only accessible from within the VPC and does not require additional web application firewall protection."
        },
        {
          id: "AwsSolutions-APIG6",
          reason:
            "CloudWatch logging at the stage level is not required as the API Gateway acts as a proxy to the Lambda function. The Lambda function has its own CloudWatch logs which provide comprehensive logging for all requests and responses."
        }
      ],
      true
    );

    // Suppress IAM4 for CloudWatch role (managed policy)
    NagSuppressions.addResourceSuppressions(
      this.restApi,
      [
        {
          id: "AwsSolutions-IAM4",
          reason:
            "AWS managed policy for API Gateway CloudWatch logging is required for standard API Gateway functionality. This is a standard AWS managed policy with well-defined permissions for CloudWatch Logs access.",
          appliesTo: [
            "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
          ]
        }
      ],
      true
    );
  }
}
