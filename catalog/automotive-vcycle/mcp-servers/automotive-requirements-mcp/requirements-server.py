#!/usr/bin/env python3
"""
MCP Server for Automotive Requirements Analysis using AWS Bedrock AgentCore Runtime
"""

import json
import logging
import os
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Annotated

import boto3
import requests
import yaml
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_agent_config_from_yaml(yaml_path: str = None) -> Dict[str, Any]:
    """
    Load agent configuration from .bedrock_agentcore.yaml file
    
    Args:
        yaml_path: Optional path to the YAML file. If not provided, searches for it.
    
    Returns:
        Dictionary containing agent configuration
    """
    if yaml_path is None:
        # Search for .bedrock_agentcore.yaml in common locations
        search_paths = [
            ".bedrock_agentcore.yaml",
            "./catalog/automotive-vcycle/requirements-agent/.bedrock_agentcore.yaml"
        ]

        # Log current working directory for debugging
        logger.info(f"Current working directory: {os.getcwd()}")
        
        yaml_path = None
        for path in search_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                yaml_path = expanded_path
                logger.info(f"Found .bedrock_agentcore.yaml at: {expanded_path}")
                break
        
        if yaml_path is None:
            logger.warning("Could not find .bedrock_agentcore.yaml file, using fallback configuration")
            return get_fallback_config()
    
    try:
        with open(yaml_path, 'r') as file:
            yaml_config = yaml.safe_load(file)
        
        # Extract the default agent configuration
        default_agent_name = yaml_config.get('default_agent')
        if not default_agent_name:
            logger.error("No default_agent specified in YAML config")
            return get_fallback_config()
        
        agent_config = yaml_config.get('agents', {}).get(default_agent_name)
        if not agent_config:
            logger.error(f"Agent '{default_agent_name}' not found in YAML config")
            return get_fallback_config()
        
        # Extract bedrock_agentcore configuration
        bedrock_config = agent_config.get('bedrock_agentcore', {})
        aws_config = agent_config.get('aws', {})
        auth_config = agent_config.get('authorizer_configuration')
        
        # Construct the agent configuration
        config = {
            "agent_id": bedrock_config.get('agent_id'),
            "agent_arn": bedrock_config.get('agent_arn'),
            "agent_session_id": str(uuid.uuid4()),
            "region": aws_config.get('region', 'us-west-2'),
            "authorizer_configuration": auth_config
        }
        
        # Validate required fields
        if not all([config["agent_id"], config["agent_arn"], config["agent_session_id"]]):
            logger.error("Missing required fields in YAML config")
            return get_fallback_config()
        
        logger.info(f"Successfully loaded agent config for: {default_agent_name}")
        return config
        
    except Exception as e:
        logger.error(f"Error loading YAML config: {str(e)}")
        return get_fallback_config()

def get_fallback_config() -> Dict[str, Any]:
    """
    Fallback configuration if YAML file cannot be loaded
    """
    logger.info("Using fallback agent configuration")
    return {
        "agent_id": "automotive_requirements_analyzer_inbound_auth_xxx",
        "agent_arn": "arn:aws:bedrock-agentcore:us-west-2:account-id:runtime/automotive_requirements_analyzer_inbound_auth_xxx",
        "agent_session_id": "xxx",  # Must be 33+ chars
        "region": "us-west-2",
        "authorizer_configuration": {
            "customJWTAuthorizer": {
                "discoveryUrl": "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_xxx/.well-known/openid-configuration",
                "allowedClients": ["xxx"]
            }
        }
    }

# Load agent configuration from YAML file
AGENT_CONFIG = load_agent_config_from_yaml()

# Initialize FastMCP server
mcp = FastMCP("automotive-requirements-mcp")

class AutomotiveRequirementsAgent:
    def __init__(self):
        self.cognito_client = None
        self.bearer_token = None
        self.token_expiry = 0
        
        # Get Cognito credentials from environment
        self.client_id = os.getenv("COGNITO_CLIENT_ID")
        self.username = os.getenv("COGNITO_USERNAME")
        self.password = os.getenv("COGNITO_PASSWORD")
        
        if not all([self.client_id, self.username, self.password]):
            logger.warning("Cognito credentials not found in environment. Authentication will be required per request.")
    
    def get_cognito_client(self):
        """Initialize Cognito client if not already done"""
        if self.cognito_client is None:
            self.cognito_client = boto3.client(
                'cognito-idp',
                region_name=AGENT_CONFIG["region"]
            )
        return self.cognito_client
    
    def get_bearer_token(self):
        """Get a valid bearer token, refreshing if necessary"""
        current_time = time.time()
        
        # Check if we have a valid token (with 5 minute buffer)
        if self.bearer_token and current_time < (self.token_expiry - 300):
            return self.bearer_token
        
        # Need to get a new token
        if not all([self.client_id, self.username, self.password]):
            raise Exception("Cognito credentials not configured. Cannot generate bearer token.")
        
        try:
            cognito_client = self.get_cognito_client()
            
            auth_response = cognito_client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": self.username,
                    "PASSWORD": self.password
                }
            )
            
            self.bearer_token = auth_response["AuthenticationResult"]["AccessToken"]
            # Tokens typically expire in 1 hour (3600 seconds)
            self.token_expiry = current_time + 3600
            
            logger.info("Successfully obtained new bearer token")
            return self.bearer_token
            
        except Exception as e:
            logger.error(f"Failed to obtain bearer token: {str(e)}")
            raise Exception(f"Authentication failed: {str(e)}")
    
    def invoke_agent(self, requirements_docs: str, bearer_token: Optional[str] = None) -> dict:
        """Invoke the AgentCore runtime agent with requirements documents for analysis
        uses low level http requests as AgentCoreRuntime API does not support bearer tokens as of now.
        See: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-oauth.html"""

        try:
            # Use provided bearer token or get one automatically
            if bearer_token:
                auth_token = bearer_token
                logger.info("Using provided bearer token")
            else:
                # Try to get bearer token automatically if credentials are configured
                try:
                    auth_token = self.get_bearer_token()
                    logger.info("Using automatically generated bearer token")
                except Exception as e:
                    logger.warning(f"Could not generate bearer token automatically: {str(e)}")
                    raise Exception(f"Authentication failed: {str(e)}")
            
            # URL encode the agent ARN
            escaped_agent_arn = urllib.parse.quote(AGENT_CONFIG["agent_arn"], safe='')
            
            # Construct the URL
            url = f"https://bedrock-agentcore.{AGENT_CONFIG['region']}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"
            
            # Set up headers
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-Amzn-Trace-Id": "111", #dummy number, backend assigns a unique trace-id
                "Content-Type": "application/json",
                "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": AGENT_CONFIG["agent_session_id"]
            }
            
            # Prepare the payload
            payload = {"requirements_docs": requirements_docs}
            
            # Make the HTTP request
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=900
            )
            
            logger.info(f"AgentCore API response status: {response.status_code}")
            
            # Handle response based on status code
            if response.status_code == 200:
                response_data = response.json()
                logger.info("Agent response received successfully")
                return response_data
            elif response.status_code >= 400:
                error_data = response.json() if response.content else {"error": "Unknown error"}
                logger.error(f"AgentCore API error ({response.status_code}): {error_data}")
                raise Exception(f"AgentCore API error ({response.status_code}): {error_data}")
            else:
                logger.error(f"Unexpected status code: {response.status_code}")
                raise Exception(f"Unexpected status code: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request error: {str(e)}")
            raise Exception(f"Failed to invoke AgentCore agent: {str(e)}")
        except Exception as e:
            logger.error(f"Error invoking agent: {str(e)}")
            raise Exception(f"Failed to invoke AgentCore agent: {str(e)}")

# Initialize the agent
agent = AutomotiveRequirementsAgent()

@mcp.tool(
    description="Analyze automotive business requirements documents for consistency and generate user acceptance tests. Supply absolute file paths of documents to analyze."
)
def automotive_requirements_analyzer(
    requirements_docs: Annotated[str, "Absolute file path to the business requirements documents (BRD) to analyze for consistency and UAT generation"]
) -> str:
    """
    Analyze automotive business requirements documents for consistency and generate user acceptance tests.
    
    This tool implements a multi-step automotive requirements analyzer using agent graph with:
    1. Requirements Consistency Analysis (checks for completeness, quality, and automotive standards)
    2. User Acceptance Test Generation (always generates comprehensive test specifications)
    
    Authentication is handled automatically using Cognito credentials from environment variables.
    
    Parameters
    ----------
    requirements_docs : str
        Absolute file path to the business requirements documents (BRD) to analyze for consistency and UAT generation
    
    Returns
    -------
    str
        JSON string containing:
        - Graph execution metrics
        - Requirements consistency analysis results
        - User acceptance test generation results
        
    Examples
    --------
    >>> result = automotive_requirements_analyzer(
    ...     requirements_docs="/path/to/requirements_brd.md"
    ... )
    """
    if not requirements_docs.strip():
        return json.dumps({
            "error": "No requirements document path provided for analysis",
            "step1_requirements_analysis": {"analysis": "No requirements provided", "issues": []},
            "step2_user_acceptance_tests": {"generated": False, "reason": "No requirements provided"}
        })
    
    try:
        # Read the requirements document from file
        try:
            with open(requirements_docs, 'r', encoding='utf-8') as f:
                requirements_content = f.read()
            logger.info(f"Successfully read requirements document from: {requirements_docs}")
        except FileNotFoundError:
            return json.dumps({
                "error": f"Requirements document not found at path: {requirements_docs}",
                "step1_requirements_analysis": {"analysis": "File not found", "issues": []},
                "step2_user_acceptance_tests": {"generated": False, "reason": "Requirements file not found"}
            })
        except Exception as e:
            return json.dumps({
                "error": f"Failed to read requirements document: {str(e)}",
                "step1_requirements_analysis": {"analysis": "File read error", "issues": []},
                "step2_user_acceptance_tests": {"generated": False, "reason": f"Requirements read error: {str(e)}"}
            })
        
        # Invoke the multi-agent automotive requirements analyzer with the extracted content
        result = agent.invoke_agent(requirements_content)
        
        # Return the structured result as JSON string
        return json.dumps(result, indent=2)
        
    except Exception as e:
        error_result = {
            "error": f"Analysis failed: {str(e)}",
            "step1_requirements_analysis": {"analysis": "Analysis failed", "issues": []},
            "step2_user_acceptance_tests": {"generated": False, "reason": "Analysis failed"}
        }
        return json.dumps(error_result, indent=2)

if __name__ == "__main__":
    mcp.run()