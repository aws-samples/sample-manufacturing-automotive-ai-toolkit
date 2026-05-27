#  C Code Analyzer and Test Generator
Multi-agent system for automotive C code analysis with custom automotive coding standards compliance checking and unit test generation.

## Overview

The system uses a **conditional sequential graph** pattern with 2 nodes:

1. **Automotive Coding Standards Analysis**: Analyzes C code for custom automotive coding standards violations
2. **Unit Test Generation**: If no severe violations are found, generates comprehensive unit tests

## Architecture

```
┌─────────────────────┐    Condition: No HIGH     ┌─────────────────────┐
│ Automotive Analyzer │────severity violations───▶│  Unit Test Generator│
│   (Entry Point)     │                           │  (Conditional Node) │
└─────────────────────┘                           └─────────────────────┘
```

- **Node 1**: Automotive Coding Standards Analyzer - Identifies safety-critical violations (Entry Point)
- **Node 2**: Unit Test Generator - Creates automotive-grade unit tests (Conditional Execution)
- **Graph Pattern**: Strands GraphBuilder with conditional edges
- **Authentication**: Amazon Cognito with JWT tokens
- **Runtime**: Amazon Bedrock AgentCore Runtime
- **Model**: Amazon Nova 2 Lite

## Key Features

### Graph-Based Multi-Agent System
- Uses Strands GraphBuilder for agent orchestration
- Conditional sequential execution pattern
- Automatic workflow control based on analysis results
- Performance metrics and execution tracking

### Automotive Coding Standards Compliance Checking
- Detects custom automotive coding standards violations
- Categorizes violations by severity (LOW, MEDIUM, HIGH)
- Focuses on automotive safety standards
- Prevents unit test generation for code with severe violations

### Unit Test Generation
- Generates comprehensive unit tests for C functions
- Includes edge cases and boundary conditions
- Follows automotive testing standards
- Creates tests suitable for safety-critical applications
- Returns generated tests as response content
- Includes test result tracking and assertion macros

### Multi-Agent Graph Workflow
- Conditional execution based on compliance analysis results using GraphBuilder
- Structured response with both analysis and test generation results
- Clear separation of concerns between graph nodes
- Execution metrics and performance tracking
- Automatic workflow control based on automotive coding standards violation severity

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
- For Kiro, extend the default setup in the workspace (`./kiro` folder) by adding the c-code analyzer configuration. Add additional steering file under '/ide-support/kiro'
- For Cline, use `./ide-support/cline`.
- Adjust the Cognito Client-Id from your deployment from step 1.
- Adjust your local Python path to the `c_code_analyzer.py` if necessary.
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

## Sample Test Cases

The notebook includes three test cases using files from `sample_automotive_code/`:

1. **Severe Violations** (`sample_with_severe_violations.c`): C code with malloc/free usage (blocks unit test generation)
2. **Minor Violations** (`sample_with_minor_violations.c`): C code with C++ style comments (allows unit test generation)
3. **Compliant Code** (`sample_automotive_compliant.c`): Automotive-compliant C code (generates comprehensive unit tests)

## Custom Automotive Coding Standards Checked

- **AUTO-STYLE-001**: Use C-style comments for better compiler compatibility across automotive toolchains
- **AUTO-SAFE-001**: External function declarations must be visible at definition point for safety traceability
- **AUTO-FUNC-001**: Function return values must be checked for error handling in automotive systems
- **AUTO-MEM-001**: Dynamic memory allocation is prohibited in safety-critical automotive systems

## Security

- Inbound authentication using Amazon Cognito
- JWT token validation
- IAM role-based permissions
- Secure deployment on AgentCore Runtime

