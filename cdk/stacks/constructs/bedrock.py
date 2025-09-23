"""
Bedrock construct for managing Bedrock agents and configurations
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_bedrock as bedrock,
    aws_iam as iam,
    aws_lambda as lambda_,
)
from constructs import Construct
from typing import Dict, Any, List, Optional


class BedrockConstruct(Construct):
    """
    Construct for managing Bedrock agents and their configurations.
    
    This construct creates and manages Bedrock agents, but in the current
    implementation, the actual agent creation is handled by the Vista agents
    nested stack. This construct provides a foundation for future Bedrock
    agent management if needed.
    """

    def __init__(self, scope: Construct, construct_id: str, 
                 foundation_model: str,
                 agent_role: iam.Role,
                 lambda_functions: Dict[str, lambda_.Function],
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.foundation_model = foundation_model
        self.agent_role = agent_role
        self.lambda_functions = lambda_functions
        
        # Store references for potential future use
        self.specialist_agents: Dict[str, Any] = {}
        self.supervisor_agent: Optional[Any] = None
        
        print(f"BedrockConstruct initialized with model: {foundation_model}")
        print(f"Available Lambda functions: {list(lambda_functions.keys())}")

    def get_foundation_model(self) -> str:
        """Get the foundation model ID"""
        return self.foundation_model

    def get_agent_role(self) -> iam.Role:
        """Get the Bedrock agent execution role"""
        return self.agent_role

    def get_lambda_functions(self) -> Dict[str, lambda_.Function]:
        """Get all available Lambda functions"""
        return self.lambda_functions

    def add_specialist_agent(self, agent_name: str, agent_config: Dict[str, Any]) -> None:
        """Add a specialist agent configuration (for future use)"""
        self.specialist_agents[agent_name] = agent_config
        print(f"Added specialist agent configuration: {agent_name}")

    def set_supervisor_agent(self, supervisor_config: Dict[str, Any]) -> None:
        """Set the supervisor agent configuration (for future use)"""
        self.supervisor_agent = supervisor_config
        print("Set supervisor agent configuration")

    def get_agent_summary(self) -> Dict[str, Any]:
        """Get a summary of all configured agents"""
        return {
            'foundation_model': self.foundation_model,
            'specialist_agents_count': len(self.specialist_agents),
            'has_supervisor': self.supervisor_agent is not None,
            'specialist_agents': list(self.specialist_agents.keys())
        }