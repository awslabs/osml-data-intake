# Data Intake – CDK Infrastructure

This CDK project deploys the core infrastructure for running **Data Intake** on AWS.

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
    "VPC_NAME": "<YOUR-VPC-NAME>"
  },
  "dataplaneConfig": {
    "BUILD_FROM_SOURCE": <true/false>,
    "CONTAINER_URI": "<CONTAINER-IMAGE-URI>",
    "LAMBDA_FUNCTION_NAME": "<LAMBDA-FUNCTION-NAME>",
    "LAMBDA_MEMORY_SIZE": <MEMORY-IN-MB>,
    "LAMBDA_TIMEOUT": <TIMEOUT-IN-SECONDS>,
    "S3_OUTPUT_BUCKET_NAME": "<OUTPUT-BUCKET-NAME>",
    "SNS_INPUT_TOPIC_NAME": "<INPUT-TOPIC-NAME>",
    "SNS_STAC_TOPIC_NAME": "<STAC-OUTPUT-TOPIC-NAME>"
  }
}
```

💡 This file is validated at runtime to ensure all required fields are provided. Deployment will fail if any required fields are missing or invalid.

### VPC Configuration

The CDK application creates a VPC that is used by the data intake stack. VPC configuration is handled through the `networkConfig` section in your deployment.json:

- **If `networkConfig.VPC_NAME` is provided**: Creates or uses a VPC with the specified name
- **If `networkConfig` is not provided**: Creates a new VPC with sensible defaults:
  - Public and private subnets across 2 availability zones
  - NAT Gateway for private subnet internet access
  - CIDR block: `10.0.0.0/16`

**Example configurations:**

Create new VPC with defaults:

```json
{
  "projectName": "DataIntake",
  "account": {
    "id": "123456789012",
    "region": "us-west-2",
    "prodLike": false,
    "isAdc": false
  }
}
```

Create VPC with custom name:

```json
{
  "projectName": "DataIntake",
  "account": {
    "id": "123456789012",
    "region": "us-west-2",
    "prodLike": false,
    "isAdc": false
  },
  "networkConfig": {
    "VPC_NAME": "data-intake-vpc"
  }
}
```

### Data Intake Configuration

The CDK stack demonstrates the Data Intake deployment. All configuration is centralized in the `deployment.json` file through the optional `dataplaneConfig` section, which uses the `DataIntakeConfig` type from the local constructs, eliminating the need to modify TypeScript code for customization.

For the complete list of configuration parameters and their defaults, refer to the `DataIntakeConfig` class in `lib/data-intake-stack.ts`.

#### Example: Custom Configuration

To customize the Data Intake, simply add the `dataIntakeConfig` section to your `deployment.json` file like the example below:

```json
{
  "dataplaneConfig": {
    "BUILD_FROM_SOURCE": false,
    "CONTAINER_URI": "awsosml/osml-data-intake-intake:latest",
    "LAMBDA_FUNCTION_NAME": "DataIntakeFunction",
    "LAMBDA_MEMORY_SIZE": 2048,
    "LAMBDA_TIMEOUT": 900,
    "S3_OUTPUT_BUCKET_NAME": "my-data-intake-output",
    "SNS_INPUT_TOPIC_NAME": "my-data-intake-input",
    "SNS_STAC_TOPIC_NAME": "my-data-intake-stac-output"
  }
}
```

#### Building Containers from Source

By default, the CDK uses the pre-built container image from the registry. To build the container from source instead, set `BUILD_FROM_SOURCE: true` in your configuration:

```json
{
  "dataplaneConfig": {
    "BUILD_FROM_SOURCE": true
  }
}
```

**Note**: When building from source, ensure Docker is installed and running on your deployment machine. The build process will use the appropriate Dockerfile in the docker directory.

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
cdk deploy --all
```

This command will:

- Validate `deployment.json`
- Synthesize the CloudFormation template
- Deploy the infrastructure to your AWS account

**Note**: CDK will display the changes that will be made and prompt you to approve them before proceeding with the deployment. Review the changes carefully and type `y` to confirm the deployment.

#### Automated Deployment

For automated deployments or CI/CD pipelines, we recommend using:

```bash
cdk deploy --all --require-approval never --concurrency 2
```

This command will:

- Deploy all stacks in the application
- Skip interactive approval prompts
- Automatically proceed with deployment changes
- Deploy multiple stacks in parallel (up to 2 concurrent deployments)

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
│   ├── data-intake-stack.ts          # Main Data Intake CDK stack
│   ├── network-stack.ts              # Network infrastructure stack
│   └── constructs/                   # Modular construct classes
│       ├── shared/                   # Shared components
│       │   ├── osml-account.ts       # Account configuration interface
│       │   ├── osml-vpc.ts           # VPC and networking resources
│       │   ├── osml-bucket.ts        # S3 bucket management
│       │   ├── osml-container.ts     # Container image handling
│       │   └── utils/                # Utility classes
│       │       ├── base-config.ts    # Base configuration class
│       │       └── regional-config.ts # Regional configuration
│       └── data-intake/              # Data intake specific constructs
│           ├── di-dataplane.ts       # Main data intake dataplane
│           └── roles/                # IAM roles
│               └── di-lambda-role.ts # Lambda execution roles
├── test/                             # Unit tests and cdk-nag checks
│   └── test-utils.ts                 # Test utilities
└── package.json                      # Project config and npm
```

---

## 🏗️ Architecture

This CDK project uses a **modular construct architecture** that separates concerns into focused, reusable classes:

### Core Constructs

- **`Account`** - Account configuration interface
- **`NetworkConfig`** - Network configuration management
- **`DataIntakeConfig`** - Data intake configuration management
- **`Vpc`** - Manages VPC creation with sensible defaults
- **`Bucket`** - S3 bucket management with proper encryption and policies
- **`Container`** - Container image handling for build-from-source scenarios
- **`DIDataplane`** - Main orchestrator for data intake resources
- **`DILambdaRole`** - IAM roles for Lambda function execution

### Benefits

- **Modularity**: Each construct has a single, clear responsibility
- **Reusability**: Constructs can be used independently or in other projects
- **Maintainability**: Easier to debug, test, and modify specific functionality
- **Type Safety**: Full TypeScript support with proper interfaces
- **Self-contained**: No external dependencies on osml-cdk-constructs

### Usage Example

```typescript
// Access specific resources through the main dataplane
const dataplane = new DIDataplane(this, "DIDataplane", { ... });

// Direct access to resource groups
const roles = dataplane.roles;
const buckets = dataplane.buckets;
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

### Security Features

- **S3 Encryption**: All S3 buckets use AES-256 encryption by default
- **IAM Roles**: Least privilege access patterns for Lambda functions
- **VPC Isolation**: Private subnets for compute resources
- **Resource Tagging**: Proper tagging for resource management and cost allocation

For deeper hardening guidance, refer to:

- [AWS CDK Security and Safety Dev Guide](https://docs.aws.amazon.com/cdk/v2/guide/security.html)
- Use of [`CliCredentialsStackSynthesizer`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.CliCredentialsStackSynthesizer.html) for controlling credential use

---

## 🔄 Migration from osml-cdk-constructs

This CDK application contains constructs that were previously part of the shared `osml-cdk-constructs` library:

- **Migrated constructs**: `di_*` prefixed constructs for data intake functionality
- **Shared dependencies**: Common constructs like OSMLAccount, OSMLVpc, OSMLBucket
- **Self-contained**: No external dependencies on osml-cdk-constructs
- **Independent deployment**: Can be deployed without other OSML components

### Benefits of Migration

- **Independence**: No dependency on shared construct library
- **Faster iteration**: Changes don't require updates to shared library
- **Version control**: Each service controls its own infrastructure version
- **Simplified CI/CD**: Independent build and deployment pipelines

---

## 🧠 Summary

This CDK project provides infrastructure-as-code for deploying overhead imagery data intake capabilities using AWS native services. It includes security validations via cdk-nag and supports deployment across multiple environments through configuration files.

The project follows the same architectural patterns as the OSML Model Runner, ensuring consistency across the OSML ecosystem while maintaining independence and modularity.

For questions or contributions, please open an issue or PR.
