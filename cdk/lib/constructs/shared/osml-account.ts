/*
 * Copyright 2023-2024 Amazon.com, Inc. or its affiliates.
 */
/**
 * Represents a deployment account configuration.
 *
 * @interface Account
 */
export interface Account {
  /**
   * The unique identifier of the account.
   *
   * @type {string}
   * @memberof Account
   */
  id: string;

  /**
   * The region where the account is deployed.
   *
   * @type {string}
   * @memberof Account
   */
  region: string;

  /**
   * Indicates whether the account is configured as a production-like environment.
   *
   * @type {boolean}
   * @memberof Account
   */
  prodLike: boolean;

  /**
   * Indicates whether the account is configured as an ADC region
   *
   * @type {boolean}
   * @memberof Account
   */
  isAdc?: boolean;
}
