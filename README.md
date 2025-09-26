# Manufacturing & Automotive AI Toolkit (MA3T)

A collection of sample AI agents for Automotive and Manufacturing use cases.

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

### 2. Bedrock Model Access
Enable access to required models in your AWS account:
- Go to AWS Bedrock Console → Model access
- Request access to:
  - `anthropic.claude-3-haiku-20240307-v1:0` (Used by VISTA agents, default for AgentCore)
  - `us.anthropic.claude-3-7-sonnet-20250219-v1:0` (Used by the frontend UI)

### 3. Setup Environment
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

![MA3T User Interface](docs/ui.png)

## Architecture

The MA3T architecture consists of:

1. **Agent Catalog**: A collection of agents implemented using various frameworks
   - Standalone Agents: Individual agents for specific tasks
   - Multi-Agent Collaborations: Groups of agents that work together

2. **Agent Frameworks**:
   - AWS Bedrock Agents: Native, managed Bedrock agents
   - AgentCore Agents: Container-based agents using the Bedrock AgentCore framework
      - Support for Strands, LangGraph, CrewAI, and LlamaIndex

3. **UI Framework**: A Next.js+React-based user interface for interacting with agents
   - Single pane of glass for all agents
   - Automatic agent discovery and registration
   - Basic authentication for secure access

4. **Deployment Framework**: CDK for deploying agents to AWS

## Contributing

We welcome additional agent examples to the framework. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

To contribute an idea for an agent, please open an issue. If you'd like to contribute your own example, follow the instructions in [developing.md](/docs/developing.md).

## License

This project is licensed under MIT - see the [LICENSE](LICENSE) file for details.