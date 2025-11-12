/*
 * Copyright 2023-2024 Amazon.com, Inc. or its affiliates.
 */

import { RemovalPolicy } from "aws-cdk-lib";
import {
  BlockPublicAccess,
  Bucket as S3Bucket,
  BucketAccessControl,
  BucketEncryption,
  IBucket,
  ObjectOwnership
} from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";

/**
 * Represents the properties required to configure the Bucket Construct.
 *
 * @interface BucketProps
 */
export interface BucketProps {
  /**
   * The name of the bucket.
   *
   * @type {string}
   */
  bucketName: string;

  /**
   * Indicates whether the bucket should be configured for production-like usage.
   *
   * @type {boolean}
   */
  prodLike: boolean;

  /**
   * The removal policy to apply to the bucket when it is deleted or removed from the stack.
   * This defines how the bucket and its contents should be handled.
   *
   * @type {RemovalPolicy}
   */
  removalPolicy: RemovalPolicy;

  /**
   * (Optional) The access logs bucket where access logs for the bucket should be stored.
   * If not provided, access logs may not be enabled or stored separately.
   *
   * @type {IBucket | undefined}
   */
  accessLogsBucket?: IBucket;
}

/**
 * Represents a Bucket construct with access logging.
 */
export class OSMLBucket extends Construct {
  /**
   * The core bucket for storing objects.
   */
  public bucket: S3Bucket;

  /**
   * Optional access logging bucket for storing access logs.
   */
  public accessLogsBucket?: IBucket;

  /**
   * Creates a Bucket and optionally an Access Logging Bucket.
   * @param {Construct} scope - The scope/stack in which to define this construct.
   * @param {string} id - The id of this construct within the current scope.
   * @param {BucketProps} props - The properties of this construct.
   * @returns OSMLBucket - The Bucket construct.
   */
  constructor(scope: Construct, id: string, props: BucketProps) {
    super(scope, id);

    // Set up shared properties for our bucket and access logging bucket
    const bucketProps = {
      autoDeleteObjects: !props.prodLike,
      enforceSSL: true,
      encryption: BucketEncryption.KMS_MANAGED,
      blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
      removalPolicy: props.removalPolicy,
      objectOwnership: ObjectOwnership.OBJECT_WRITER
    };

    // Check if an access logging bucket is provided or needs to be created
    if (props.accessLogsBucket === undefined && props.prodLike) {
      // Create an accessing logging bucket for the core bucket
      this.accessLogsBucket = new S3Bucket(
        this,
        `${id}AccessLogs`,
        Object.assign(bucketProps, {
          bucketName: `${props.bucketName}-access-logs`,
          accessControl: BucketAccessControl.LOG_DELIVERY_WRITE,
          versioned: props.prodLike
        })
      );
    } else if (props.prodLike) {
      // Import the existing access logging bucket
      this.accessLogsBucket = props.accessLogsBucket;
    }

    // Create the core bucket with optional access logging
    this.bucket = new S3Bucket(
      this,
      id,
      Object.assign(bucketProps, {
        bucketName: props.bucketName,
        versioned: props.prodLike,
        accessControl: BucketAccessControl.BUCKET_OWNER_FULL_CONTROL,
        serverAccessLogsBucket: this.accessLogsBucket
      })
    );
  }
}
