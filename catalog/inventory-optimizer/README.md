# Inventory Optimizer - AgentCore

An intelligent inventory management system for e-bike manufacturing using Amazon Bedrock AgentCore with the Strands framework.

## Overview

This agent helps optimize inventory decisions for an e-bike manufacturer with a production facility in Seattle and distribution centers in New York and Los Angeles. The system analyzes production schedules, inventory levels, supplier information, and bill of materials to make informed inventory rebalancing and procurement decisions.

The agent considers multiple factors when making recommendations:
- **Cost**: Unit pricing and transfer costs
- **Carbon Emissions**: Environmental impact of transfers and shipments
- **Lead Time**: Speed of delivery and availability

## Agent Capabilities

The Inventory Optimizer agent provides the following tools:

- **Production Planning**: Get upcoming production schedules and requirements
- **Bill of Materials**: Access product component requirements
- **Inventory Management**: Check current inventory levels across all facilities
- **Supplier Information**: Query supplier details including pricing, lead times, and emissions
- **Transfer Orders**: View pending transfers and create new transfer orders to Seattle

## Sample Prompts

Once deployed, you can test the system with these example prompts:

### Production & Inventory Analysis
- "What is the production schedule for the next 7 days?"
- "Show me current inventory levels across all locations"
- "What components are needed to build an e-bike?"
- "Check inventory levels for battery packs in Seattle"

### Supplier & Procurement
- "What suppliers do we have for motor components?"
- "Compare suppliers for battery packs based on cost and emissions"
- "Which supplier has the shortest lead time for frame components?"

### Transfer Orders
- "List all pending transfer orders"
- "We need 50 battery packs in Seattle for production tomorrow. What are my options?"
- "Transfer 100 motor units from New York to Seattle"
- "What's the most cost-effective way to get 200 frames to Seattle?"

### Decision Support
- "We have a production order for 500 e-bikes next week. Do we have enough inventory?"
- "Analyze the best option to secure 300 battery packs considering cost, emissions, and lead time"
- "Should I transfer inventory from LA or order from a supplier for urgent production needs?"

## Prerequisites

- AWS CLI configured with appropriate credentials
- Python 3.12 or later
- Node.js (for CDK)
- AWS CDK v2 installed
- Access to Amazon Bedrock with Claude Sonnet 4 model

## Model Configuration

**Current Model**: `us.anthropic.claude-sonnet-4-20250514-v1:0` (Claude Sonnet 4)

## Deployment Instructions

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt
```

### 2. Deploy Infrastructure

The agent includes CDK infrastructure that creates DynamoDB tables for:
- Customer Orders
- Inventory Levels
- Product BOM (Bill of Materials)
- Supplier Information
- Transfer Orders

```bash
# Install CDK dependencies
cd cdk
pip install -r requirements.txt

# Deploy the stack
cdk deploy
```

### 3. Deploy Agent to AgentCore

After infrastructure deployment, the agent is automatically deployed to Bedrock AgentCore via the CDK stack.

## Architecture

The system deploys:

- **AgentCore Agent** using Claude Sonnet 4 model with Strands framework
- **DynamoDB Tables** for data storage:
  - `InventoryOptimizerCustomerOrder`: Production schedules
  - `InventoryOptimizerInventoryLevel`: Current inventory across locations
  - `InventoryOptimizerProductBOM`: Product component requirements
  - `InventoryOptimizerSupplierInfo`: Supplier details and pricing
  - `InventoryOptimizerTransferOrders`: Transfer order tracking
- **IAM Roles** with appropriate permissions for DynamoDB access

## Decision Framework

When analyzing inventory optimization problems, the agent follows this framework:

1. **Transfer Existing Inventory**: Review carbon emissions, lead time, and cost for transferring from NY or LA to Seattle
2. **Order from Supplier**: Compare available suppliers considering cost, emissions, and lead time
3. **Expedite Existing Shipment**: Consider expediting with additional $10/unit cost and 500kg emissions

The agent presents all viable options and recommends the best choice based on your priorities.

## Supported Regions

Due to AgentCore regional restrictions, only these regions are supported:
- `us-east-1` (US East - N. Virginia)
- `us-west-2` (US West - Oregon) - **default**
- `eu-central-1` (Europe - Frankfurt)
- `ap-southeast-2` (Asia Pacific - Sydney)

## Clean Up

To destroy the deployed resources:

```bash
cd cdk
cdk destroy
```

## Security

- IAM roles follow least privilege principle
- All inter-service communication uses AWS IAM authentication
- DynamoDB tables are encrypted at rest

## Contributing

1. Make changes to agent code or CDK infrastructure
2. Test locally: `python agents.py`
3. Deploy to test environment: `cd cdk && cdk deploy`
4. Commit changes with descriptive message
