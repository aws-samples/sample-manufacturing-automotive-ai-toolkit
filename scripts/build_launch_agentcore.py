#!/usr/bin/env python3
"""
Deploy script for AgentCore compatible agents in MA3T framework

This script scans the agents_catalog directory for agents with type 'agentcore' in their manifest,
and deploys them using the bedrock_agentcore_starter_toolkit.
"""

import os
import json
import boto3
import logging
import argparse
from pathlib import Path
import yaml

# from bedrock_agentcore_starter_toolkit.cli.runtime.commands import configure_bedrock_agentcore

from bedrock_agentcore_starter_toolkit.operations.runtime.configure import configure_bedrock_agentcore

from bedrock_agentcore_starter_toolkit.operations.runtime.launch import launch_bedrock_agentcore
from bedrock_agentcore_starter_toolkit.utils.runtime.config import save_config
from bedrock_agentcore_starter_toolkit.utils.runtime.schema import (
    AWSConfig,
    BedrockAgentCoreAgentSchema,
    BedrockAgentCoreConfigSchema,
    BedrockAgentCoreDeploymentInfo,
    NetworkConfiguration,
    ObservabilityConfig,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('build_launch_agentcore')

def get_account_id():
    """Get the current AWS account ID"""
    sts_client = boto3.client('sts')
    return sts_client.get_caller_identity()["Account"]

def find_agentcore_agents(base_dir="agents_catalog"):
    """
    Scan the agents_catalog directory for agents with type 'agentcore' in their manifest
    
    Returns:
        List of tuples (agent_path, agent_id, agent_name, entrypoint)
    """
    agents = []
    
    # Walk through the agents_catalog directory
    for root, dirs, files in os.walk(base_dir):
        if "manifest.json" in files:
            manifest_path = os.path.join(root, "manifest.json")
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                
                # Check if any agent in the manifest is of type 'agentcore'
                for agent in manifest.get("agents", []):
                    if agent.get("type") == "agentcore":
                        agent_id = agent.get("id")
                        agent_name = agent.get("name")
                        
                        # Default entrypoint is agent.py, but can be overridden in manifest
                        entrypoint = agent.get("entrypoint", "agent.py")
                        
                        # Check if the entrypoint file exists, if not, look for alternatives
                        entrypoint_path = Path(os.path.join(root, entrypoint))
                        if not entrypoint_path.exists():
                            # Look for other potential entrypoints
                            potential_files = [f for f in files if f.endswith('.py')]
                            if potential_files:
                                # Use the first Python file as entrypoint
                                entrypoint = potential_files[0]
                                logger.warning(f"Entrypoint {agent.get('entrypoint', 'agent.py')} not found in {root}, using {entrypoint} instead")
                        
                        agents.append((root, agent_id, agent_name, entrypoint))
            except Exception as e:
                logger.error(f"Error processing manifest at {manifest_path}: {e}")
    
    return agents

def deploy_agentcore_agent(agent_path, agent_id, agent_name, entrypoint, region, execution_role_arn):
    """
    Deploy an AgentCore agent
    
    Args:
        agent_path: Path to the agent directory
        agent_id: ID of the agent
        agent_name: Name of the agent
        entrypoint: Entrypoint file for the agent
        region: AWS region
        execution_role_arn: ARN of the execution role
        
    Returns:
        dict: Deployment result with agent_arn and agent_id
    """
    logger.info(f"Deploying AgentCore agent {agent_name} from {agent_path}")
    
    try:
        # Get account ID
        account_id = get_account_id()
        
        # Create entrypoint path
        entrypoint_path = Path(os.path.join(agent_path, entrypoint))
        
        # Debug logging
        logger.info(f"Agent path: {agent_path}")
        logger.info(f"Agent ID: {agent_id}")
        logger.info(f"Agent name: {agent_name}")
        logger.info(f"Entrypoint: {entrypoint}")
        logger.info(f"Entrypoint path: {entrypoint_path}")
        
        # Change to agent directory for configuration
        original_dir = os.getcwd()
        os.chdir(agent_path)
        
        try:
            # Import the configure function
            from bedrock_agentcore_starter_toolkit.operations.runtime.configure import configure_bedrock_agentcore
            
            # Configure the agent
            logger.info(f"Configuring agent {agent_id}")
            config_result = configure_bedrock_agentcore(
                agent_name=agent_id,
                entrypoint_path=Path(entrypoint),
                execution_role=execution_role_arn,
                auto_create_ecr=True,
                enable_observability=True,
                region=region,
                container_runtime="docker",
                verbose=True
            )
            
            # Override the platform to linux/amd64 for AWS compatibility
            logger.info("Overriding platform to linux/amd64 for AWS compatibility")
            config_path = config_result.config_path
            
            # Read the current config
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            # Update platform for all agents
            if 'agents' in config_data:
                for agent_name, agent_config in config_data['agents'].items():
                    if 'platform' in agent_config:
                        logger.info(f"Changing platform from {agent_config['platform']} to linux/amd64 for agent {agent_name}")
                        agent_config['platform'] = 'linux/amd64'
            
            # Write the updated config back
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False)
            
            logger.info(f"Updated configuration saved to {config_path}")
            
            # Launch the agent
            logger.info(f"Launching agent {agent_id}")
            result = launch_bedrock_agentcore(config_path, local=False)
            
            # Extract and return deployment information
            deployment_info = {
                "agent_arn": result.agent_arn,
                "agent_id": result.agent_id,
                "ecr_uri": result.ecr_uri,
                "agent_name": agent_name
            }
            
            # Save deployment info to a file in the agent directory
            # deployment_info_path = os.path.join(agent_path, "deployment_info.json")
            # logger.info(f"Saving deployment info to {deployment_info_path}")
            # with open(deployment_info_path, 'w') as f:
            #     json.dump(deployment_info, f, indent=2)
            
            logger.info(f"Successfully deployed agent {agent_name} with ID {result.agent_id}")
            return deployment_info
            
        finally:
            # Change back to original directory
            os.chdir(original_dir)
    
    except Exception as e:
        import traceback
        logger.error(f"Error deploying agent {agent_name}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {"error": str(e), "agent_name": agent_name}

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Deploy AgentCore agents')
    parser.add_argument('--region', required=True, help='AWS region')
    parser.add_argument('--execution-role-arn', required=True, help='ARN of the execution role')
    parser.add_argument('--output-file', default='agentcore_deployment_results.json', help='Output file for deployment results')
    
    args = parser.parse_args()
    
    # Find AgentCore agents
    agents = find_agentcore_agents()
    
    if not agents:
        logger.info("No AgentCore agents found")
        return
    
    # Deploy each agent
    results = []
    for agent_path, agent_id, agent_name, entrypoint in agents:
        result = deploy_agentcore_agent(
            agent_path, 
            agent_id, 
            agent_name, 
            entrypoint, 
            args.region, 
            args.execution_role_arn
        )
        results.append(result)
    
    # Save all deployment results to the output file
    with open(args.output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Deployment results saved to {args.output_file}")
    
    # Print summary
    print("\nDeployment Summary:")
    for result in results:
        if "error" in result:
            print(f"❌ {result['agent_name']}: Failed - {result['error']}")
        else:
            print(f"✅ {result['agent_name']}: Deployed - Agent ID: {result['agent_id']}")

if __name__ == "__main__":
    main()
