# Automotive and Manufacturing GenAI Demo Library

The demo library showcases innovative AWS solutions across manufacturing and automotive use cases.

## Available Demos

Explore individual demos using the links below, or follow the installation instructions at the bottom to deploy the entire library at once.

### [In-Vehicle Agentic AI Agents (VISTA)](catalog/vista-agents-agentcore)
A multi-agent collaboration framework to improve the in-vehicle experience, with a focus on diagnostic trouble codes and service center interactions. Available in two implementations:
- **[AgentCore Version](catalog/vista-agents-agentcore)**: Container-based deployment using Amazon Bedrock AgentCore
- **[Bedrock Native Agents](catalog/vista-agents)**: Fully managed implementation using Amazon Bedrock Agents

### [Inventory Optimizer](catalog/inventory-optimizer)
An intelligent inventory management system for e-bike manufacturing using Amazon Bedrock AgentCore with the Strands framework. Analyzes production schedules, inventory levels, supplier information, and bill of materials to make informed inventory rebalancing and procurement decisions.

### [Manufacturing Quality Inspection Multi-Agent System](catalog/quality-inspection)
AI-powered quality inspection system using Amazon Nova Pro and multi-agent architecture for manufacturing defect detection and workflow automation.

### [SFC Config Generation Agent](catalog/sfc-config-agent)
An agent that accelerates industrial equipment onboarding by generating Shopfloor Connectivity (SFC) configurations for protocols like OPC-UA, Modbus, and S7, with support for multiple AWS target services.

### [Vehicle Data Discovery](catalog/vehicle-data-discovery)
A multi-agent system for autonomous vehicle fleet data discovery and HIL (Hardware-in-the-Loop) testing optimization.

---

## Full Library Installation

## Prerequisites

- AWS CLI. See the [official installation guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) for your operating system.
   ```bash
   # Verify installation and configure
   aws --version
   aws configure list
   # Verify AWS access
   aws sts get-caller-identity
   ```
- Node.js >=22 and npm installed
   ```bash
   # Verify installation
   node --version
   ```
- Python >=3.12
   ```bash
   # Ensure Python v3.12+ is installed
   python --version
   ```
- CDK CLI
   ```bash
   # Install AWS CDK CLI globally
   npm install -g aws-cdk
   # Verify installation
   cdk --version
   ```
## Bootstrap (One-time Setup)

### 1. CDK Bootstrap (if needed)
If this is your first time using CDK in this AWS account/region:
```bash
cd cdk
cdk bootstrap aws://AWS-ACCOUNT-NUMBER/us-west-2
```

>You can find your account number by running `aws sts get-caller-identity`.

### 2. Setup Environment
```bash
# Clone repository
git clone git@github.com:aws-samples/sample-manufacturing-automotive-ai-toolkit.git
cd sample-manufacturing-automotive-ai-toolkit

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r cdk/requirements.txt
```

## Deployment

### Supported Regions
Due to AgentCore regional restrictions, only these regions are supported:
- `us-east-1` (US East - N. Virginia)
- `us-west-2` (US West - Oregon) - **default**
- `eu-central-1` (Europe - Frankfurt)
- `ap-southeast-2` (Asia Pacific - Sydney)

### Deploy Command
```bash
# Interactive deployment (prompts for credentials)
./deploy_cdk.sh

# Command line with parameters
./deploy_cdk.sh --auth-user admin --auth-password yourpassword

# With custom region and account
./deploy_cdk.sh --region us-east-1 --account 123456789012 --auth-user admin --auth-password secretpass
```

### Deployment Options
- `--auth-user`: Username for UI basic authentication
- `--auth-password`: Password for UI basic authentication  
- `--region`: AWS region (must be one of the supported regions)
- `--account`: AWS account ID to deploy to (optional, uses current AWS CLI account if not specified)
- `--stack-name`: Custom CDK stack name (default: MA3TMainStack)
- `--skip-nag`: Skip CDK security checks

*Note: The CDK stack automatically triggers agent deployments via CodeBuild after successful deployment. The deployment creates an internet-accessible UI secured with basic authentication using your provided credentials.*

## Cleanup

To destroy the deployed resources:
```bash
cdk destroy --context region=us-east-1
```
*Replace `us-east-1` with the region where you deployed the stack.*

## Contributing

We welcome additional agent examples to the framework. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

To contribute an idea for an agent, please open an issue. If you'd like to contribute your own example, follow the instructions in [developing.md](/docs/developing.md).

## License

This project is licensed under MIT - see the [LICENSE](LICENSE) file for details.