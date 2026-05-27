# Automotive Requirements Analyzer and UAT Generator

The Requirements Analyzer transforms requirements documents into consistency analysis reports and comprehensive user acceptance test specifications for automotive software development.

The automotive requirements analyzer and user acceptance test generator is implemented using Strands Agents framework and deployed on Amazon Bedrock AgentCore Runtime. 


## Architecture

```
┌─────────────────┐    ┌──────────────────────────┐             ┌─────────────────┐
│   MCP Client    │───▶│  AgentCore Runtime       │──generates─▶│  Analysis &     │
│(requirements-   │    │  Requirements Agent      │             │  User Acceptance│
│    server)      │    │  (Strands)               │             │  Tests          │
└─────────────────┘    └──────────────────────────┘             └─────────────────┘
```

- **Agent**: Requirements analysis and UAT generation
- **Framework**: Strands Agents with AgentCore Runtime
- **Authentication**: Amazon Cognito with JWT tokens
- **Runtime**: Amazon Bedrock AgentCore Runtime
- **Model**: Nova 2 Lite for analysis and test generation
- **Output**: Requirements validation report and user acceptance test specifications

## Files

- `automotive_requirements_agent_notebook.ipynb` - Main Jupyter notebook demonstrating the multi-agent system
- `requirements_analyzer.py` - Full Strands-based requirements analyzer implementation
- `utils.py` - Utility functions for Cognito authentication and user pool management
- `requirements.txt` - Python dependencies for the agent to be deployed to AgentCore Runtime.


### Path Configuration

The notebook and analyzer are configured to work from the backend directory with the following path structure:

```
automotive-strands-agents-in-runtime/
├── backend/                                    # Backend Services
│   └── requirements-agent/                    # Requirements Analyzer Backend (current directory)
│       ├── automotive_requirements_agent_notebook.ipynb
│       ├── requirements_analyzer.py
│       ├── utils.py
│       └── requirements.txt
├── weather-app/business-requirements/          # Business requirements documents
│   └── weather_app_brd.md
└── weather-app/technical-requirements/         # Technical requirements documents
    └── weather_app_srs.md
```

### Key Features

1. **Business Requirements Focus**: Analyzes documents from `../weather-app/business-requirements/`
2. **Multi-Agent Architecture**: Uses Strands agents with conditional execution
3. **AgentCore Runtime**: Deploys to Amazon Bedrock AgentCore Runtime
4. **Authentication**: Integrated with Amazon Cognito for secure access
5. **User Acceptance Tests**: Generates comprehensive test specifications

## Getting Started

### Prerequisites
- Python 3.13+ (Recommended: virtual environment at workspace level created and top level requirements installed)
- AWS CLI configured for a US based region
- Amazon Bedrock access
- AgentCore Runtime permissions

### 1. Deploy Infrastructure Interactively (via Notebooks)
This section describes the deployment via notebooks. If you want to deploy via ma3t toolkit, refer to  [parent README](../README.md)

Run notebook cells. This will deploy the agent to the agentcore runtime.

### 2. Adjust the Settings/Steering Files for Local IDE
- For Kiro, use the default setup in the workspace (`./kiro` folder). 
- For Cline, use `./ide-support/cline`.
- Adjust the Cognito Client-Id from your deployment from step 1.
- Adjust your local path to the `requirements-server.py` if necessary.
- Adjust your Python path if necessary.



### Troubleshooting

If you encounter deployment issues:

1. Ensure all dependencies are installed
2. Check AWS credentials are configured
3. Review the notebook output for specific error messages

For 424 "Failed Dependency" errors, the issue is typically related to:
- Missing dependencies in requirements.txt
- Docker container build failures
- Import errors in the Python code