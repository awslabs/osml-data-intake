# OSML Data Intake – CDK Infrastructure

This CDK project deploys the core infrastructure for **OSML Data Intake** and **Data Catalog** on AWS.

---

## 📋 Prerequisites

Before deploying, ensure the following tools and resources are available:

- **AWS CLI** configured with credentials
- **AWS CDK CLI** installed (`npm install -g aws-cdk`)
- **Node.js** and **npm** installed
- **Docker** installed and running (if building container images from source)
- An existing **VPC** with private subnets and NAT Gateway (optional - a new VPC with proper networking will be created automatically if not specified)

---

## ⚙️ Configuration

### Deployment File: `bin/deployment/deployment.json`

This file defines your deployment environment. Copy the example file and customize it:

```bash
cp bin/deployment/deployment.json.example bin/deployment/deployment.json
```

Update the contents:

```json
{
  "projectName": "<YOUR-PROJECT-NAME>",
  "account": {
    "id": "<YOUR-ACCOUNT-ID>",
    "region": "<YOUR-REGION>",
    "prodLike": <true/false>,
    "isAdc": <true/false>
  },
  "networkConfig": {
    "VPC_ID": "<YOUR-VPC-ID>",
    "TARGET_SUBNETS": ["subnet-12345", "subnet-67890"],
    "SECURITY_GROUP_ID": "sg-1234567890abcdef0"
  }
}
```

💡 This file is validated at runtime to ensure all required fields are provided. Deployment will fail if any required fields are missing or invalid.

### VPC Configuration

The CDK application creates a shared VPC that is used by both the Data Intake and Data Catalog stacks. VPC configuration is handled through the `networkConfig` section in your deployment.json:

- **If `networkConfig.VPC_ID` is provided**: Uses the existing VPC with the specified ID
- **If `networkConfig.VPC_ID` is not provided**: Creates a new VPC using `Network` with sensible defaults:
  - Public and private subnets across 2 availability zones
  - NAT Gateway for private subnet internet access
  - CIDR block: `10.0.0.0/16`

**VPC Configuration Options:**

When using an existing VPC (`networkConfig.VPC_ID` provided), you can also specify:

- **`TARGET_SUBNETS`**: Array of specific subnet IDs to use for resources
- **`SECURITY_GROUP_ID`**: Security group ID to use for resources

**Example configurations:**

Create new VPC with defaults:

```json
{
  "projectName": "my-project",
  "account": {
    "id": "123456789012",
    "region": "us-west-2",
    "prodLike": false
  }
}
```

Import an existing VPC with specific subnets and security group:

```json
{
  "projectName": "my-project",
  "account": {
    "id": "123456789012",
    "region": "us-west-2",
    "prodLike": false,
    "isAdc": false
  },
  "networkConfig": {
    "VPC_ID": "vpc-abc123",
    "TARGET_SUBNETS": ["subnet-12345", "subnet-67890"],
    "SECURITY_GROUP_ID": "sg-1234567890abcdef0"
  }
}
```

**Benefits of the shared VPC approach:**

- **Resource Efficiency**: Single VPC shared between Data Intake and Data Catalog stacks reduces resource duplication
- **Consistent Network**: Both stacks use the same network configuration and security groups
- **Simplified Management**: Single VPC to manage instead of multiple separate VPCs
- **Security**: Private subnets provide additional network isolation for your workloads

This ensures efficient resource usage across both stacks while maintaining proper network isolation.

### Data Intake Configuration (Integrated)

The Data Intake components are now integrated into the Data Catalog Dataplane. All configuration is centralized in the `deployment.json` file through the `dataplaneConfig` section.

For the complete list of configuration parameters and their defaults, refer to the `DataplaneConfig` class in `lib/constructs/data-catalog/dataplane.ts`.

#### Building Data Intake Containers from Source

By default, the CDK uses the pre-built container image from the registry. To build the container from source instead, set `BUILD_FROM_SOURCE: true` in your configuration:

```json
{
  "dataplaneConfig": {
    "BUILD_FROM_SOURCE": true
  }
}
```

**Note**: When building from source, ensure Docker is installed and running on your deployment machine. The build process will use the Dockerfile.intake in the docker directory.

### Data Catalog Dataplane Configuration

The CDK stack demonstrates the Data Catalog Dataplane deployment. All configuration is centralized in the `deployment.json` file through the optional `dataplaneConfig` section, which uses the `DataplaneConfig` type from the local constructs, eliminating the need to modify TypeScript code for customization.

For the complete list of configuration parameters and their defaults, refer to the `DataplaneConfig` class in `lib/constructs/data-catalog/dataplane.ts`.

#### Example: Data Catalog Custom Configuration

To customize the Data Catalog Dataplane, simply add the `dataplaneConfig` section to your `deployment.json` file like the example below:

```json
{
  "dataplaneConfig": {
    "BUILD_FROM_SOURCE": true,
    "API_SERVICE_NAME_ABBREVIATION": "DC",
    "CONTAINER_BUILD_PATH": "lib/osml-data-intake",
    "CONTAINER_BUILD_TARGET": "ingest"
  }
}
```

#### Building Data Catalog Containers from Source

By default, the CDK uses the pre-built container image from the registry. To build the container from source instead, set `BUILD_FROM_SOURCE: true` in your configuration:

```json
{
  "dataplaneConfig": {
    "BUILD_FROM_SOURCE": true
  }
}
```

**Note**: When building from source, ensure Docker is installed and running on your deployment machine. The build process will use the appropriate Dockerfiles in the docker directory.

---

## 🚀 Deployment Instructions

### 1. Install Dependencies

```bash
npm install
```

### 2. Synthesize the Stack

```bash
cdk synth
```

### 3. Deploy the Stack

```bash
cdk deploy
```

This command will:

- Validate `deployment.json`
- Synthesize the CloudFormation template
- Deploy the infrastructure to your AWS account

**Note**: CDK will display the changes that will be made and prompt you to approve them before proceeding with the deployment. Review the changes carefully and type `y` to confirm the deployment.

**Important**: The stacks have dependencies:

- **NetworkStack** must be deployed first
- **DataCatalogStack** depends on NetworkStack (includes both data-intake and data-catalog components)

#### Automated Deployment

For automated deployments or CI/CD pipelines, we recommend using:

```bash
cdk deploy --all --require-approval never --concurrency 3
```

This command will:

- Deploy all stacks in the application
- Skip interactive approval prompts
- Automatically proceed with deployment changes
- Deploy multiple stacks in parallel (up to 3 concurrent deployments)

---

## 🧱 Project Structure

```text
cdk
├── bin/
│   ├── app.ts                        # Entry point, loads config and launches stacks
│   └── deployment/
│       ├── deployment.json           # Your environment-specific config
│       ├── deployment.json.example   # Template for creating new configs
│       └── load-deployment.ts        # Configuration loader and validator
├── lib/
│   ├── data-catalog-stack.ts         # Data Catalog CDK stack (includes data-intake components)
│   ├── network-stack.ts              # Network infrastructure CDK stack
│   └── constructs/                   # Modular construct classes
│       ├── types.ts                  # Common types and interfaces
│       └── data-catalog/             # Data Catalog constructs (includes intake components)
│           ├── dataplane.ts          # Main Data Catalog Dataplane construct
│           ├── container.ts          # Container resources
│           ├── intake-function.ts   # Lambda function for data intake
│           ├── intake-role.ts        # IAM roles for intake Lambda functions
│           ├── metadata-storage.ts   # Metadata storage resources
│           ├── ingest-function.ts    # Ingest Lambda function
│           ├── ingest-role.ts        # IAM roles for ingest functions
│           ├── network.ts            # Network - VPC and networking resources
│           ├── opensearch.ts         # OpenSearch domain
│           ├── stac-function.ts      # STAC Lambda function
│           └── stac-role.ts          # IAM roles for STAC functions
├── test/                             # Unit tests and cdk-nag checks
│   ├── data-catalog-stack.test.ts    # Data Catalog stack tests
│   ├── network-stack.test.ts         # Network stack tests
│   ├── load-deployment.test.ts       # Deployment config tests
│   └── test-utils.ts                 # Test utilities and NAG report generation
└── package.json                      # Project config and npm
```

---

## 🏗️ Architecture

This CDK project uses a **modular construct architecture** that separates concerns into focused, reusable classes:

### Core Stacks

- **`NetworkStack`** - Manages VPC creation or import (shared with Data Catalog stack)
- **`DataCatalogStack`** - Deploys both data-intake and data-catalog infrastructure (Lambda functions, S3 buckets, SNS topics, OpenSearch, STAC API, ingest functions)

### Data Catalog Constructs (includes Data Intake)

- **`Dataplane`** - Main orchestrator that combines all Data Catalog and Data Intake resources
- **`IntakeFunction`** - Manages Lambda functions for data intake processing
- **`IntakeRole`** - IAM roles for intake Lambda functions
- **`MetadataStorage`** - Manages S3 buckets and metadata storage resources
- **`Network`** - Manages VPC creation or import
- **`OpenSearch`** - Manages OpenSearch domain for catalog storage
- **`StacFunction`** - Lambda functions for STAC API operations
- **`IngestFunction`** - Lambda functions for data ingestion
- **`Container`** - Container resources for Lambda functions
- **`StacRole`** - IAM roles for STAC functions
- **`IngestRole`** - IAM roles for ingest functions

### Stack Dependencies

The stacks are deployed in a specific order due to dependencies:

1. **NetworkStack** - Creates or imports the VPC
2. **DataCatalogStack** - Depends on NetworkStack, includes both data-intake and data-catalog components

### Benefits

- **Modularity**: Each construct has a single, clear responsibility
- **Reusability**: Constructs can be used independently or in other projects
- **Maintainability**: Easier to debug, test, and modify specific functionality
- **Type Safety**: Full TypeScript support with proper interfaces

### Usage Example

```typescript
// Access all resources through the unified dataplane
const dataCatalogDataplane = new Dataplane(this, "DataCatalogDataplane", { ... });

// Direct access to resource groups
const intakeLambda = dataCatalogDataplane.intakeFunction;
const metadataStorage = dataCatalogDataplane.metadataStorage;
const ingestLambda = dataCatalogDataplane.ingestFunction;
const opensearch = dataCatalogDataplane.openSearchDomain;
```

---

## 🧪 Development & Testing

### Useful Commands

| Command         | Description                                          |
| --------------- | ---------------------------------------------------- |
| `npm run build` | Compile TypeScript to JavaScript                     |
| `npm run watch` | Auto-recompile on file changes                       |
| `npm run test`  | Run Jest unit tests                                  |
| `cdk synth`     | Generate CloudFormation template                     |
| `cdk diff`      | Compare local stack with deployed version            |
| `cdk deploy`    | Deploy the CDK stack                                 |
| `cdk destroy`   | Remove the deployed stack                            |
| `cdk bootstrap` | Bootstrap CDK in your AWS account (first-time setup) |
| `cdk list`      | List all stacks in the app                           |

---

## 🔐 Security & Best Practices

This project integrates **cdk-nag** to validate infrastructure against AWS security best practices. Running `npm run test` will:

- Detect overly permissive IAM roles and security groups
- Ensure encryption is enabled where applicable
- Warn about missing logging or compliance settings

📄 **Review the cdk-nag report** to maintain compliance and security posture before production deployments.

### CDK-NAG Report Generation

The test suite automatically generates comprehensive cdk-nag compliance reports during test execution. The reporting system works as follows:

#### How Reports Are Generated

1. **During Test Execution**: Each stack test (`data-catalog-stack.test.ts`, `network-stack.test.ts`, etc.) runs cdk-nag's `AwsSolutionsChecks` and calls `generateNagReport()` which:
   - Extracts errors and warnings from stack annotations
   - Collects suppressed violations from stack template metadata
   - Displays a formatted compliance report to stdout
   - Aggregates suppressed violations for the final report

2. **After All Tests Complete**: The Jest global teardown hook (configured in `jest.config.js`) automatically calls `generateFinalSuppressedViolationsReport()`, which:
   - Consolidates all suppressed violations from all test stacks
   - Generates a comprehensive report file: `cdk-nag-suppressions-report.txt`
   - Includes summary statistics by rule type and detailed breakdowns by stack

#### Report Files

After running tests, you'll find:

- **`cdk-nag-suppressions-report.txt`**: Comprehensive report of all suppressed NAG violations across all stacks
  - Summary by rule type showing violation counts
  - Detailed breakdown per stack with resource-level information
  - Suppression reasons for each violation

#### Viewing Reports

```bash
# Run tests to generate reports
npm run test

# View the final suppressed violations report
cat cdk-nag-suppressions-report.txt
```

#### Understanding Suppressions

The report distinguishes between:

- **Errors**: Unsuppressed violations that need to be fixed
- **Warnings**: Unsuppressed warnings that should be reviewed
- **Suppressed Violations**: Violations that have been explicitly suppressed with documented reasons

Each suppressed violation includes:

- The NAG rule that was suppressed (e.g., `AwsSolutions-S1`)
- The resource where the suppression applies
- The reason for suppression (as documented in the code)

For deeper hardening guidance, refer to:

- [AWS CDK Security and Safety Dev Guide](https://docs.aws.amazon.com/cdk/v2/guide/security.html)
- Use of [`CliCredentialsStackSynthesizer`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.CliCredentialsStackSynthesizer.html) for controlling credential use

---

## 🧠 Summary

This CDK project provides infrastructure-as-code for deploying data intake and catalog capabilities using AWS native services. It includes security validations via cdk-nag and supports deployment across multiple environments through configuration files.

For questions or contributions, please open an issue or PR.
