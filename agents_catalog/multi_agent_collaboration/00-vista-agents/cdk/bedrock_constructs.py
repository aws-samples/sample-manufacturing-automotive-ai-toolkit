"""
Custom CDK Constructs for Bedrock Multi-Agent Collaboration
Based on AWS Community best practices
"""

import json
from typing import List, Dict, Any, Optional
import aws_cdk as cdk
from aws_cdk import (
    aws_bedrock as bedrock,
    aws_lambda as lambda_,
    aws_iam as iam,
)
from constructs import Construct


class ActionGroup:
    """Helper class for creating action groups from configuration"""
    
    @staticmethod
    def from_config(action_group_config: Dict[str, Any], lambda_function: lambda_.Function) -> bedrock.CfnAgent.AgentActionGroupProperty:
        """Create action group from configuration dictionary"""
        
        # Handle both API schema and function schema configurations
        schema_config = None
        if "api_schema" in action_group_config:
            schema_config = bedrock.CfnAgent.APISchemaProperty(
                payload=json.dumps(action_group_config["api_schema"])
            )
        elif "function_schema" in action_group_config:
            schema_config = bedrock.CfnAgent.FunctionSchemaProperty(
                functions=action_group_config["function_schema"]["functions"]
            )
        
        return bedrock.CfnAgent.AgentActionGroupProperty(
            action_group_name=action_group_config["action_group_name"],
            description=action_group_config.get("description", ""),
            action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                lambda_=lambda_function.function_arn
            ),
            api_schema=schema_config if "api_schema" in action_group_config else None,
            function_schema=schema_config if "function_schema" in action_group_config else None
        )


class Agent(Construct):
    """Custom CDK Construct for Bedrock Agents with Multi-Agent Collaboration support"""
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        agent_name: str,
        agent_description: str,
        agent_instruction: str,
        foundation_model: str,
        agent_resource_role_arn: str,
        action_groups: Optional[List[bedrock.CfnAgent.AgentActionGroupProperty]] = None,
        **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)
        
        self.agent_name = agent_name
        self.agent_description = agent_description
        self.collaborators = []
        
        # Create the Bedrock agent
        self.agent = bedrock.CfnAgent(
            self,
            f"{construct_id}Agent",
            agent_name=agent_name,
            description=agent_description,
            agent_resource_role_arn=agent_resource_role_arn,
            foundation_model=foundation_model,
            instruction=agent_instruction,
            action_groups=action_groups if action_groups else None,
            idle_session_ttl_in_seconds=1800
        )
        
        # Store for later access
        self.agent_id = self.agent.attr_agent_id
        self.agent_arn = self.agent.attr_agent_arn
        
    def create_alias(self, alias_name: str) -> bedrock.CfnAgentAlias:
        """Create an alias for the agent"""
        self.alias = bedrock.CfnAgentAlias(
            self,
            f"{self.agent_name}Alias",
            agent_alias_name=alias_name,
            agent_id=self.agent_id
        )
        return self.alias
    
    def enable_collaboration(self, how: str = "SUPERVISOR_ROUTER"):
        """Enable collaboration for this agent"""
        # Note: In CDK 2.99.1, we may need to use lower-level constructs
        # This method sets up the agent to act as a supervisor
        self.collaboration_mode = how
        
        # Update the agent with collaboration settings if supported
        # For now, we'll track this and apply it during agent creation
        pass
    
    def add_collaborator(
        self, 
        collaborator_alias: bedrock.CfnAgentAlias,
        collaborator_name: str, 
        collaboration_instruction: str,
        relay_conversation_history: str = "DISABLED"
    ):
        """Add a collaborator to this supervisor agent"""
        collaborator_config = {
            "alias": collaborator_alias,
            "name": collaborator_name,
            "instruction": collaboration_instruction,
            "relay_history": relay_conversation_history
        }
        self.collaborators.append(collaborator_config)
        
        # For CDK 2.99.1, we may need to handle this differently
        # Store the configuration for later use
        print(f"Registered collaborator: {collaborator_name}")


class MultiAgentSupervisor(Agent):
    """Specialized Agent that acts as a supervisor with routing capabilities"""
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        agent_name: str,
        foundation_model: str,
        agent_resource_role_arn: str,
        agent_description: Optional[str] = None,
        agent_instruction: Optional[str] = None,
        **kwargs
    ):
        # Use provided description or default
        if agent_description is None:
            agent_description = "Vehicle Service Management Supervisor"
        
        # Use provided instruction or default
        if agent_instruction is None:
            agent_instruction = """
            You are a vehicle service management supervisor agent that coordinates with specialized agents to provide comprehensive customer service.
            
            Based on the customer's request, route to the appropriate specialist:
            - For vehicle symptoms and diagnostics: Route to vehicle symptom analysis
            - For finding dealers: Route to dealer lookup
            - For booking appointments: Route to appointment booking
            - For parts information: Route to parts availability
            - For warranty information: Route to warranty lookup
            - For checking dealer availability: Route to dealer availability
            
            Always provide helpful, accurate information and ensure smooth handoffs between agents.
            Maintain context throughout the conversation and provide summaries when appropriate.
            """
        
        super().__init__(
            scope=scope,
            construct_id=construct_id,
            agent_name=agent_name,
            agent_description=agent_description,
            agent_instruction=agent_instruction,
            foundation_model=foundation_model,
            agent_resource_role_arn=agent_resource_role_arn,
            **kwargs
        )
        
        # Enable collaboration mode - this will be configured after all agents are created
        self.collaboration_mode = "SUPERVISOR_ROUTER"
        
    def finalize_collaboration(self):
        """Finalize the multi-agent collaboration configuration"""
        if not self.collaborators:
            print("Warning: No collaborators registered for supervisor agent")
            return
            
        # Create agent collaborator properties with correct CloudFormation structure
        collaborator_properties = []
        for collab in self.collaborators:
            # Use the correct CloudFormation property structure for AgentCollaborators
            collaborator_prop = {
                "AgentDescriptor": {
                    "AliasArn": collab["alias"].attr_agent_alias_arn
                },
                "CollaboratorName": collab["name"],
                "CollaborationInstruction": collab["instruction"],
                "RelayConversationHistory": collab.get("relay_history", "DISABLED")
            }
            collaborator_properties.append(collaborator_prop)
        
        # Configure the agent with collaboration enabled from the start
        # This avoids the in-place update issue
        self.agent.add_property_override("AgentCollaboration", "SUPERVISOR_ROUTER")
        self.agent.add_property_override("AgentCollaborators", collaborator_properties)
        
        print(f"Configured supervisor agent with {len(collaborator_properties)} collaborators")


class SpecialistAgent(Agent):
    """Specialized Agent for specific vehicle service functions"""
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        agent_name: str,
        agent_description: str,
        agent_instruction: str,
        foundation_model: str,
        agent_resource_role_arn: str,
        action_groups: Optional[List[bedrock.CfnAgent.AgentActionGroupProperty]] = None,
        **kwargs
    ):
        super().__init__(
            scope=scope,
            construct_id=construct_id,
            agent_name=agent_name,
            agent_description=agent_description,
            agent_instruction=agent_instruction,
            foundation_model=foundation_model,
            agent_resource_role_arn=agent_resource_role_arn,
            action_groups=action_groups,
            **kwargs
        )
