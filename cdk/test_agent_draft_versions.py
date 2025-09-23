#!/usr/bin/env python3
"""
Test agent DRAFT versions to check action group configuration
"""

import json
import sys
import boto3
from botocore.exceptions import ClientError

def test_draft_versions():
    """Test DRAFT versions of agents to see action group configuration"""
    
    bedrock_agent = boto3.client('bedrock-agent')
    
    # Get Vista agents
    response = bedrock_agent.list_agents()
    vista_agents = [agent for agent in response.get('agentSummaries', []) if 'SAM-agent' in agent.get('agentName', '')]
    
    for agent in vista_agents:
        agent_id = agent['agentId']
        agent_name = agent['agentName']
        
        print(f"\n🔍 Checking DRAFT version for: {agent_name}")
        
        try:
            # Get the agent (which returns DRAFT version by default)
            response = bedrock_agent.get_agent(agentId=agent_id)
            agent_detail = response['agent']
            
            action_groups = agent_detail.get('actionGroups', [])
            print(f"  📋 DRAFT version has {len(action_groups)} action groups")
            
            if action_groups:
                for i, ag in enumerate(action_groups):
                    ag_name = ag.get('actionGroupName', f'ActionGroup{i}')
                    ag_state = ag.get('actionGroupState', 'UNKNOWN')
                    print(f"    🔧 {ag_name}: {ag_state}")
                    
                    # Check executor
                    executor = ag.get('actionGroupExecutor')
                    if executor and executor.get('lambda'):
                        print(f"       Lambda: {executor['lambda']}")
                    
                    # Check schema
                    if ag.get('apiSchema'):
                        print(f"       Has API schema")
                    elif ag.get('functionSchema'):
                        print(f"       Has function schema")
                        # Print function schema details
                        func_schema = ag.get('functionSchema', {})
                        functions = func_schema.get('functions', [])
                        print(f"       Functions: {len(functions)}")
                        for func in functions:
                            func_name = func.get('name', 'Unknown')
                            print(f"         - {func_name}")
            
            # Check if we need to prepare the agent
            agent_status = agent_detail.get('agentStatus', 'UNKNOWN')
            print(f"  📋 Agent status: {agent_status}")
            
            if agent_status == 'NOT_PREPARED' and action_groups:
                print(f"  ⚠️  Agent has action groups but is NOT_PREPARED - needs preparation")
                
                # Prepare the agent
                try:
                    print(f"  🔄 Preparing agent...")
                    prepare_response = bedrock_agent.prepare_agent(agentId=agent_id)
                    print(f"  ✅ Agent preparation initiated")
                    print(f"     Status: {prepare_response.get('agentStatus', 'Unknown')}")
                except ClientError as e:
                    print(f"  ❌ Error preparing agent: {e}")
            
        except ClientError as e:
            print(f"  ❌ Error getting agent details: {e}")

if __name__ == "__main__":
    test_draft_versions()