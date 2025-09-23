# AgentCore Deployment Test Report

## Summary
- **Total Tests**: 5
- **Passed**: 3
- **Failed**: 2

## Local Discovery
✅ **Status**: PASSED

**Agents Found**: 1

**Agents**: [
  {
    "path": "/Users/agweber/code/old-amazon-bedrock-agents-healthcare-lifesciences/agents_catalog/standalone_agents/00-products-agent",
    "id": "template-agent",
    "name": "Product Knowledge Agent",
    "entrypoint": "knowledge_base_agent.py",
    "manifest": {
      "id": "template-agent",
      "name": "Product Knowledge Agent",
      "description": "",
      "type": "agentcore",
      "entrypoint": "knowledge_base_agent.py",
      "tags": [
        "tag1",
        "tag2"
      ]
    },
    "has_dockerfile": true,
    "has_requirements": true,
    "has_agentcore_config": true
  }
]

## Script Test
✅ **Status**: PASSED

**Agents Discovered**: 1

**Agent Details**: [
  {
    "path": "agents_catalog/standalone_agents/00-products-agent",
    "id": "template-agent",
    "name": "Product Knowledge Agent",
    "entrypoint": "knowledge_base_agent.py"
  }
]

## Codebuild Projects
❌ **Status**: FAILED

**Total Projects**: 0

**Agentcore Projects**: 0

**Project Details**: []

## Toolkit Availability
✅ **Status**: PASSED

**Version Info**: {
  "Name": "bedrock-agentcore-starter-toolkit",
  "Version": "0.1.0",
  "Summary": "A starter toolkit for using Bedrock AgentCore",
  "Home-page": "https://github.com/aws/bedrock-agentcore-starter-toolkit",
  "Author": "",
  "Author-email": "AWS <opensource@amazon.com>",
  "License": "Apache-2.0",
  "Location": "/Users/agweber/code/old-amazon-bedrock-agents-healthcare-lifesciences/.venv/lib/python3.12/site-packages",
  "Requires": "bedrock-agentcore, boto3, botocore, docstring-parser, httpx, jinja2, prompt-toolkit, pydantic, pyyaml, requests, rich, toml, typer, typing-extensions, urllib3, uvicorn",
  "Required-by": ""
}

## Permissions
❌ **Status**: FAILED

**Error**: 'BedrockAgentCoreDataPlaneFrontingLayer' object has no attribute 'list_agents'

