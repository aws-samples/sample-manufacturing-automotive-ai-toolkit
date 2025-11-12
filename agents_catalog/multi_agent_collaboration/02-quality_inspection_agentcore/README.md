# Manufacturing Quality Inspection Multi-Agent System

AI-powered quality inspection system using Amazon Nova Pro and multi-agent architecture for manufacturing defect detection and workflow automation.

## 🏭 System Overview

This system implements a complete manufacturing quality inspection pipeline using:
- **Amazon Nova Pro** for visual defect detection
- **Multi-Agent Architecture** with Strands framework
- **Real-time Processing** with S3 and DynamoDB integration
- **SNS Notifications** for quality alerts
- **Complete Audit Trail** across all manufacturing decisions

![Quality Inspection Target Architecture](docs/quality_inspection_target_architecture.png)

## 🤖 Agent Architecture

The system follows a sequential workflow with 5 specialized agents:

### 1. Vision Agent
- **Purpose**: Defect detection using computer vision
- **Technology**: Amazon Nova Pro multimodal AI
- **Input**: Manufacturing part images vs reference
- **Output**: Defect classification, coordinates, and measurements

### 2. Analysis Agent
- **Purpose**: Intelligent reasoning and quality assessment
- **Technology**: Advanced AI analysis of vision data
- **Input**: Vision agent results and quality standards
- **Output**: Detailed defect analysis and quality recommendations

### 3. SOP Agent  
- **Purpose**: Apply Standard Operating Procedures
- **Rules**: Manufacturing quality compliance and disposition logic
- **Input**: Analysis agent recommendations
- **Output**: Final disposition decisions (accept/rework/scrap)

### 4. Action Agent
- **Purpose**: Execute physical manufacturing actions
- **Actions**: File routing, production control, workflow execution
- **Input**: SOP disposition decisions
- **Output**: S3 operations, production system updates

### 5. Communication Agent
- **Purpose**: ERP integration and stakeholder notifications
- **Systems**: SAP, MES, SNS alerts, production dashboards
- **Input**: Action execution results
- **Output**: System updates, quality alerts, audit logs

## 🚀 Quick Start

### Prerequisites
- AWS Account with Bedrock access
- Python 3.10+
- AWS CLI configured

### Local Development
```bash
# Clone repository
git clone <repository-url>
cd manufacturing-quality-agents

# Install dependencies
pip install -r requirements.txt

# Deploy AWS infrastructure
cd infrastructure
cdk deploy

# Run Streamlit application
streamlit run src/streamlit_multi_agent_app_modular.py
```

### AgentCore Deployment
```bash
# Install AgentCore CLI
pip install bedrock-agentcore-starter-toolkit

# Deploy all agents to AgentCore
cd src/agents
./deploy_to_agentcore.sh

# Test deployment
python test_agentcore_agents.py
```

## 📁 Project Structure

```
manufacturing-quality-agents/
├── src/                          # Source code
│   ├── agents/                   # Multi-agent implementations
│   ├── vision/                   # Computer vision modules
│   ├── utils/                    # Utility functions
│   └── streamlit_multi_agent_app.py
├── scripts/                      # Setup and utility scripts
│   ├── setup_infrastructure.sh   # AWS resource creation
│   ├── create_dynamodb_tables.py # Database setup
│   └── setup_s3_buckets.py      # S3 bucket creation
├── infrastructure/               # Infrastructure as Code (CDK)
│   ├── app.py                   # CDK application entry point
│   ├── quality_inspection_stack.py # CDK stack definition
│   ├── cdk.json                 # CDK configuration
│   ├── requirements.txt         # CDK dependencies
│   └── README.md                # CDK deployment guide
├── config/                       # Configuration files
│   └── settings.yaml            # Application settings
├── docs/                        # Documentation
├── tests/                       # Test files
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## 🔧 Configuration

Update `config/settings.yaml` with your AWS settings:
```yaml
aws:
  region: us-east-1
  s3_bucket: your-bucket-name
  sns_topic_arn: your-sns-topic-arn

agents:
  model_id: amazon.nova-pro-v1:0
  temperature: 0.1
```

## 📊 Data Flow

1. **Image Upload** → S3 `inputimages/` folder
2. **Vision Analysis** → Nova Pro defect detection with coordinates
3. **Quality Analysis** → AI-powered defect assessment and reasoning
4. **SOP Compliance** → Rule-based disposition decisions
5. **Physical Actions** → File routing and production control
6. **Communications** → ERP updates, alerts, and audit logging

## 🗄️ Database Schema

### DynamoDB Tables
- `vision-inspection-data` - Vision analysis results
- `sop-decisions` - SOP compliance decisions
- `action-execution-log` - Physical action logs
- `erp-integration-log` - ERP system updates
- `historical-trends` - Quality trend data
- `sap-integration-log` - SAP integration logs

## 🔔 Notifications

- **Quality Alerts**: SNS notifications for defects
- **Production Updates**: ERP system integration
- **Trend Reports**: Automated quality analytics

## 🧪 Testing

```bash
# Run unit tests
python -m pytest tests/

# Test batch processing
python src/batch_defect_processor.py

# Test individual components
python tests/test_vision_agent.py
```

## 📈 Monitoring

- **Agent Logs**: Real-time execution tracking
- **Processing History**: Complete workflow audit
- **Quality Metrics**: Defect rates and trends
- **System Health**: AWS CloudWatch integration
- **AgentCore Observability**: Built-in monitoring and tracing

## 🌐 Deployment Options

### 1. Local Development
- Streamlit web application
- Direct agent invocation
- Local testing and debugging

### 2. AWS Lambda
- Serverless deployment
- Event-driven processing
- CDK infrastructure

### 3. Amazon Bedrock AgentCore
- Managed agent runtime
- Auto-scaling and load balancing
- Built-in memory and observability
- See [AgentCore Deployment Guide](docs/AGENTCORE_DEPLOYMENT.md)

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in this repository
- Check the documentation in `/docs`
- Review the troubleshooting guide

## 🔮 Roadmap

- [ ] Real-time streaming processing
- [ ] Advanced ML model integration
- [ ] Mobile app for quality inspectors
- [ ] Integration with more ERP systems
- [ ] Predictive maintenance algorithms

## 🚀 Quick Deployment Commands

### Redeploy Orchestrator Agent
```bash
./scripts/deploy_orchestrator.sh
```

### Key System Information
- **Orchestrator Runtime ARN**: `arn:aws:bedrock-agentcore:us-east-1:975672448831:runtime/quality_inspection_orchestrator-d4T2R9GSN4`
- **S3 Bucket**: `machinepartimages-975672448831`
- **DynamoDB Table**: `vision-inspection-data`
- **ECR Repository**: `bedrock-agentcore-quality_inspection_orchestrator`