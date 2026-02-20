#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0
01-sfc-config-agent
SFC Config generation Agent - Accelerate Industrial Equipment Onboarding.
"""

import sys
import os
import json
from pathlib import Path
from dotenv import load_dotenv

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# Import the externalized functions
from src.tools.file_operations import SFCFileOperations
from src.tools.prompt_logger import PromptLogger
from src.tools.sfc_knowledge import load_sfc_knowledge

# Load environment variables from .env file (only once per process)
_env_loaded = False
if not _env_loaded:
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        _env_loaded = True
    else:
        # Try to load from repo root
        repo_env_path = Path(__file__).parent.parent.parent.parent / ".env"
        if repo_env_path.exists():
            load_dotenv(dotenv_path=repo_env_path)
            _env_loaded = True
        else:
            _env_loaded = True

# Global AWS Bedrock configuration - configure once, use everywhere
AWS_BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
)
AWS_BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

# S3/DynamoDB storage configuration for agent-generated files
# Resolution order: env var → SSM parameter (set by CDK stack) → default
# SSM parameters /sfc-config-agent/s3-bucket-name and /sfc-config-agent/ddb-table-name
# are created by SfcConfigAgentStack and read at runtime by file_operations.py

try:
    from strands import Agent, tool
    from strands.models import BedrockModel
    from mcp import stdio_client, StdioServerParameters
    from strands.tools.mcp import MCPClient
    from bedrock_agentcore.runtime import BedrockAgentCoreApp
    from contextlib import asynccontextmanager
except ImportError:
    sys.exit(1)

# Configure logging
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)

# Global variables for lazy initialization
_mcp_client = None
_agent = None


def initialize_mcp_client():
    """Initialize MCP client - called on first request"""
    global _mcp_client
    
    if _mcp_client is not None:
        return _mcp_client
    
    try:
        # Get MCP server configuration from environment variables
        mcp_command = os.getenv("MCP_SERVER_COMMAND", "python")
        
        # Construct absolute path to MCP server
        agent_dir = os.path.dirname(os.path.abspath(__file__))
        mcp_server_path = os.path.join(agent_dir, "sfc-spec-mcp-server.py")
        
        if not os.path.exists(mcp_server_path):
            raise FileNotFoundError(f"MCP server not found at {mcp_server_path}")
        
        # Allow override from environment, but default to absolute path
        mcp_args_str = os.getenv("MCP_SERVER_ARGS", mcp_server_path)
        
        # Parse comma-separated args
        mcp_args = [arg.strip() for arg in mcp_args_str.split(",")]
        
        _mcp_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command=mcp_command,
                    args=mcp_args,
                )
            )
        )
        
        _mcp_client.start()
        return _mcp_client
        
    except Exception as e:
        logger.error(f"Failed to initialize MCP client: {str(e)}")
        return None

@asynccontextmanager
async def lifespan(app):
    """Application lifespan manager for startup and cleanup."""
    yield  # Application runs here
    
    # Cleanup
    if _mcp_client is not None:
        try:
            _mcp_client.stop()
        except Exception as e:
            logger.error(f"Error stopping MCP client: {e}")


# Initialize AgentCore app with lifespan manager
app = BedrockAgentCoreApp(lifespan=lifespan)


def _validate_bedrock_service_access(
    session: boto3.Session, region: str, model_id: str
) -> tuple[bool, str]:
    """Validate that a Bedrock boto3 client can be created.

    Args:
        session: Boto3 session
        region: AWS region
        model_id: Bedrock model ID (unused, kept for interface compatibility)

    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        session.client("bedrock", region_name=region)
        return (True, "")
    except Exception as e:
        return (
            False,
            f"Failed to create Bedrock client in region {region}: {str(e)}",
        )


def _validate_aws_credentials() -> tuple[bool, str]:
    """Validate AWS credentials for Bedrock access.

    Returns:
        tuple: (is_valid, error_message)
    """
    if not BOTO3_AVAILABLE:
        return (
            False,
            "boto3 not available. Please install boto3 to use AWS Bedrock.",
        )

    try:
        session = boto3.Session()
        credentials = session.get_credentials()

        if not credentials:
            return (
                False,
                "No AWS credentials found.",
            )

        region = AWS_BEDROCK_REGION
        model_id = AWS_BEDROCK_MODEL_ID

        is_valid, error_msg = _validate_bedrock_service_access(
            session, region, model_id
        )
        if not is_valid:
            return (False, error_msg)

        return (True, "")

    except ProfileNotFound as e:
        return (False, f"AWS profile not found: {str(e)}")
    except NoCredentialsError:
        return (
            False,
            "No AWS credentials found.",
        )
    except Exception as e:
        return (
            False,
            f"Unexpected error validating credentials: {str(e)}",
        )


class SFCWizardAgent:
    """
    AWS Shopfloor Connectivity (SFC) Wizard Agent
    Specialized for debugging existing configurations, creating new ones,
    testing configurations, and defining environments.
    """

    def __init__(self):
        self.sfc_knowledge = load_sfc_knowledge()
        self.current_config = None
        self.validation_errors = []
        self.recommendations = []

        # Initialize the prompt logger (stores conversations in S3/DynamoDB)
        self.prompt_logger = PromptLogger(max_history=20)

        # Validate AWS credentials during initialization
        self.aws_credentials_valid, self.aws_credentials_error = (
            _validate_aws_credentials()
        )

        # Initialize the Strands agent with SFC-specific tools
        self.agent = self._create_agent()

    def _create_agent(self) -> Agent:
        """Create a Strands agent with SFC-specific tools"""

        @tool
        def read_config_from_file(filename: str) -> str:
            """Read an SFC configuration JSON file from cloud storage (S3 bucket with DynamoDB index).

            Looks up the file first in the DynamoDB metadata table for fast retrieval,
            then falls back to scanning the S3 bucket under the configs/ prefix.

            Args:
                filename: Name of the config file to read (e.g. 'my-config.json')
            """
            return SFCFileOperations.read_config_from_file(filename)

        @tool
        def save_config_to_file(config_json: str, filename: str) -> str:
            """Save an SFC configuration as a JSON file to cloud storage (S3 bucket and DynamoDB index).

            The file is uploaded to the S3 artifacts bucket under a date-partitioned prefix
            (year=YYYY/month=MM/day=DD/hour=HH/) and indexed in the DynamoDB files table.
            The tool returns a pre-signed S3 download URL as a markdown hyperlink.
            IMPORTANT: Always include the pre-signed download link from the tool response
            in your reply to the user so they can download the saved file directly.

            Args:
                config_json: SFC configuration JSON string to save
                filename: Name of the file to save the configuration to (e.g. 'my-config.json')
            """
            return SFCFileOperations.save_config_to_file(config_json, filename)

        @tool
        def save_results_to_file(content: str, filename: str) -> str:
            """Save content to cloud storage (S3 bucket and DynamoDB index) with specified extension (txt, vm, md).

            The file is uploaded to the S3 artifacts bucket under a date-partitioned prefix
            (year=YYYY/month=MM/day=DD/hour=HH/) and indexed in the DynamoDB files table.
            The tool returns a pre-signed S3 download URL as a markdown hyperlink.
            IMPORTANT: Always include the pre-signed download link from the tool response
            in your reply to the user so they can download the saved file directly.

            Args:
                content: Content to save to the file
                filename: Name of the file to save (defaults to .txt extension if none provided)
            """
            return SFCFileOperations.save_results_to_file(content, filename)

        @tool
        def save_conversation(count: int = 1) -> str:
            """Save the last N conversation exchanges as markdown files to cloud storage (S3 and DynamoDB).

            Each file contains a user prompt and the agent's response, formatted in markdown.
            Files are stored in the S3 artifacts bucket under a date-partitioned prefix
            (year=YYYY/month=MM/day=DD/hour=HH/) and indexed in DynamoDB.
            The tool returns a pre-signed S3 download URL as a markdown hyperlink.
            IMPORTANT: Always include the pre-signed download link from the tool response
            in your reply to the user so they can download the saved file directly.

            Args:
                count: Number of recent conversations to save (default: 1)
            """
            try:
                success, message = self.prompt_logger.save_n_conversations(count)
                if success:
                    return message
                else:
                    return f"Error: {message}"
            except Exception as e:
                return f"Error saving conversations: {str(e)}"

        @tool
        def read_context_from_file(file_path: str) -> str:
            """Read content from cloud storage (S3 bucket and DynamoDB) to use as context.

            Searches across all S3 prefixes (configs/, results/, conversations/, runs/) and the
            DynamoDB metadata table to find and retrieve the file. Supports JSON, Markdown, CSV,
            TXT, and VM files.

            Args:
                file_path: Filename or S3 key of the file to read

            Returns:
                String containing the file content or error message
            """
            success, message, content = SFCFileOperations.read_context_from_file(
                file_path
            )
            if success and content:
                return f"{message}\n\n```\n{content}\n```"
            else:
                return message

        # Store internal tools as instance variable for use by initialize_agent
        self.agent_internal_tools = [
            read_config_from_file,
            save_config_to_file,
            save_results_to_file,
            save_conversation,
            read_context_from_file,
        ]

        # Agent will be created lazily by initialize_agent()
        return None


def initialize_agent():
    """Initialize agent with MCP tools - called on first request"""
    global _agent
    
    if _agent is not None:
        return _agent
    
    try:
        # Create SFCWizardAgent instance to get tools
        wizard = SFCWizardAgent()
        
        # Initialize MCP client
        mcp_client = initialize_mcp_client()
        
        # Get MCP tools
        mcp_tools = []
        if mcp_client:
            try:
                mcp_tools = mcp_client.list_tools_sync()
            except Exception as e:
                logger.warning(f"Could not load MCP tools: {str(e)}")
        else:
            logger.warning("MCP client not available, agent will use internal tools only")
        
        # Agent system prompt
        agent_system_prompt = """You are a specialized assistant for creating, validating & running SFC (stands for "Shop Floor Connectivity") configurations.
        "Use your MCP (shall be your main resource for validation) and internal tools to gather required information.
        "Always explain your reasoning and cite sources when possible.
        "Keep your responses clean and professional. Do not use icons or emojis unless they are truly essential to convey meaning (e.g., a warning symbol for critical errors). Prefer plain text for clarity."""
        
        # Create agent with Bedrock model and all tools
        try:
            bedrock_model = BedrockModel(
                model_id=AWS_BEDROCK_MODEL_ID, 
                region_name=AWS_BEDROCK_REGION
            )
            
            _agent = Agent(
                model=bedrock_model,
                tools=wizard.agent_internal_tools + mcp_tools,
                system_prompt=agent_system_prompt,
            )
            
        except Exception as model_error:
            logger.error(f"Error creating agent with Bedrock model: {str(model_error)}")
            _agent = Agent(tools=wizard.agent_internal_tools)
        
        return _agent
        
    except Exception as e:
        logger.error(f"Failed to initialize agent: {str(e)}")
        raise RuntimeError(f"Agent initialization failed: {str(e)}")


@app.entrypoint
def invoke(payload):
    """AgentCore entrypoint for HTTP requests - processes user input and returns response"""
    try:
        agent = initialize_agent()
        
        if agent is None:
            raise RuntimeError("Agent not initialized. Check application startup logs.")
        
        # Extract prompt from payload
        user_message = payload.get("prompt", "")
        if not user_message:
            return {
                "error": "No prompt found in input. Please provide a 'prompt' key in the input."
            }
        
        # Direct agent call (synchronous, suitable for HTTP)
        response = agent(user_message)
        return {"result": response.message}
            
    except Exception as e:
        logger.error(f"Agent processing failed: {str(e)}")
        return {
            "error": f"Agent processing failed: {str(e)}"
        }

if __name__ == "__main__":
    app.run()