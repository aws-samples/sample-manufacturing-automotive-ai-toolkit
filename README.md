# Manufacturing & Automotive AI Toolkit (MA3T)

A toolkit to accelerate the adoption of agentic AI in the Automotive & Manufacturing industry, providing a flexible framework for implementing AI agents.

## Framework Todo
- [] Deployment
   - [x] Deploy Bedrock Native Agents
   - [x] Deploy AgentCore Agents
   - [x] Build UI w/ CodeBuild
   - [] Deploy UI
- [x] Add example for Bedrock-based Cfn
- [x] Add example for AgentCore w/ Strands
- [] Add example for AgentCore w/MCP
- [] Only pull Bedrock agents by tag
- [] Multi agents with mixed types
- [] Test 1-click on Github
- [] Change HCLS to MA3T

## AWS Samples Todo
- [] Confirm repo name and change internal links
- [] Add/confirm license to top of all files
- [] Set up Git secret and search codebase

## Deployment
MA3T supports deployment via cloning this repository to your local machine and launching via a shell script or via one-click deploy.

### From Local Machine
```bash
./deploy.sh --stack-name ma3t-toolkit-stack --bucket ma3t-toolkit-XXXXXXXXXXXX-us-west-2 --region us-west-2
```

### One-Click Deploy
...

## Architecture
The MA3T architecture consists of:

1. **Agent Catalog**: A collection of agents implemented using various frameworks
   - Standalone Agents: Individual agents for specific tasks
   - Multi-Agent Collaborations: Groups of agents that work together

2. **Agent Frameworks**:
   - AWS Bedrock Agents: Native, managed Bedrock agents
   - AgentCore Agents: Container-based agents using the Bedrock AgentCore framework
      - Support for Strands, LangGraph, CrewAI, and LlamaIndex
   - ~~Jupyter Notebook Agents: Agents implemented as Jupyter notebooks~~

3. **UI Framework**: A Next.js+React-based user interface for interacting with agents
   - Single pane of glass for all agents
   - Automatic agent discovery and registration

4. **Deployment Framework**: CloudFormation templates for deploying agents to AWS

## Adding an Agent
MA3T supports native Bedrock Agents and AgentCore packaged agents.

All agents must have a `manifest.json` file in their root directory. This file is used by the UI to automatically register agents and by the deployment scripts to discover and deploy agents.

Your agent must sit within `agents_catalog/multi_agent_collaboration` or `agents_catalog/standalone_agents`.

### AgentCore Agents

Paired with a manifest file, AgentCore agents are automatically deployed as containers to AWS and can be integrated with the MA3T UI with no additional code needed.

To create an AgentCore agent:

1. Create a new directory in the agents_catalog` with your agent name
2. Create a manifest.json file with the following structure:
   ```json
   {
     "agents": [
       {
         "id": "your-agent-id",
         "name": "Your Agent Name",
         "type": "agentcore",
         "entrypoint": "your_agent_file.py",
         "tags": ["tag1", "tag2"]
       }
     ]
   }
   ```
3. Create your agent implementation file (e.g., `your_agent_file.py`) using the AgentCore framework
4. The agent will be automatically deployed when you run the CloudFormation deployment



## Contributing

We welcome contributions to the MA3T! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

This project is licensed under MIT - see the [LICENSE](LICENSE) file for details.