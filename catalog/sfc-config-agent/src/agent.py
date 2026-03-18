#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0
sfc-config-agent
SFC Config generation Agent - Accelerate Industrial Equipment Onboarding.
"""

import sys
import os
from datetime import datetime
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

# Global AWS / model configuration
AWS_BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
)
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
AWS_BEDROCK_INFERENCE_REGION = os.getenv("AWS_BEDROCK_INFERENCE_REGION", "us-east-1")


# AgentCore Memory ID — resolved lazily on first request
MEM_ID = None

# Current session ID — set at the start of each invoke() call
CURRENT_SESSION_ID = None
    
try:
    from strands import Agent, tool
    from strands.models import BedrockModel
    from mcp import stdio_client, StdioServerParameters
    from strands.tools.mcp import MCPClient
    from bedrock_agentcore.runtime import BedrockAgentCoreApp
    from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
    from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
    from contextlib import asynccontextmanager
except ImportError:
    sys.exit(1)

# Configure logging
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)

# Global variables for lazy initialization
_mcp_client = None
_bedrock_model = None
_agent_tools = None


def initialize_mcp_client():
    """Initialize MCP client - called on first request"""
    global _mcp_client

    if _mcp_client is not None:
        return _mcp_client

    try:
        mcp_command = os.getenv("MCP_SERVER_COMMAND", "python")

        agent_dir = os.path.dirname(os.path.abspath(__file__))
        mcp_server_path = os.path.join(agent_dir, "sfc-spec-mcp-server.py")

        if not os.path.exists(mcp_server_path):
            raise FileNotFoundError(f"MCP server not found at {mcp_server_path}")

        mcp_args_str = os.getenv("MCP_SERVER_ARGS", mcp_server_path)
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
    """Validate that a Bedrock boto3 client can be created."""
    try:
        session.client("bedrock", region_name=region)
        return (True, "")
    except Exception as e:
        return (
            False,
            f"Failed to create Bedrock client in region {region}: {str(e)}",
        )


def _validate_aws_credentials() -> tuple[bool, str]:
    """Validate AWS credentials for Bedrock access."""
    if not BOTO3_AVAILABLE:
        return (
            False,
            "boto3 not available. Please install boto3 to use AWS Bedrock.",
        )

    try:
        session = boto3.Session()
        credentials = session.get_credentials()

        if not credentials:
            return (False, "No AWS credentials found.")

        is_valid, error_msg = _validate_bedrock_service_access(
            session, AWS_BEDROCK_INFERENCE_REGION, AWS_BEDROCK_MODEL_ID
        )
        if not is_valid:
            return (False, error_msg)

        return (True, "")

    except ProfileNotFound as e:
        return (False, f"AWS profile not found: {str(e)}")
    except NoCredentialsError:
        return (False, "No AWS credentials found.")
    except Exception as e:
        return (False, f"Unexpected error validating credentials: {str(e)}")


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

            The file is uploaded to the S3 artifacts bucket under configs/YYYY/MM/DD/HH/<filename>
            and a control-plane record (configId/version/name/s3Key) is written to DynamoDB so
            the config appears in the Control Plane UI Config Browser.
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

            The file is uploaded to the S3 artifacts bucket under results/YYYY/MM/DD/HH/<filename>
            and indexed in the DynamoDB files table.
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
            Files are stored in the S3 artifacts bucket under conversations/YYYY/MM/DD/HH/
            and indexed in DynamoDB.
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

        @tool
        def retrieve_session_memory(actor_id: str = "sfc-agent-user") -> str:
            """Retrieve stored memory records for the current session from AgentCore Memory.

            Use this tool when the user asks about previous interactions,
            prior context, earlier steps, or what was discussed before in this session.
            The session is determined automatically from the current request context.

            Args:
                actor_id: The actor/user identifier (default: 'sfc-agent-user').
            """
            if not MEM_ID or not CURRENT_SESSION_ID:
                return "Session context is not yet initialised. Please retry after the first request has been processed."
            try:
                client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)
                namespace = f"{actor_id}/{CURRENT_SESSION_ID}"
                response = client.list_memory_records(
                    memoryId=MEM_ID,
                    namespace=namespace,
                )
                records = response.get("memoryRecords", [])
                if not records:
                    return f"No memory records found for session '{CURRENT_SESSION_ID}' (actor: '{actor_id}')."

                lines = [f"Memory records for session '{CURRENT_SESSION_ID}' (actor: '{actor_id}'):"]
                for i, rec in enumerate(records, start=1):
                    content = rec.get("content", {})
                    text = content.get("text", "") if isinstance(content, dict) else str(content)
                    created = rec.get("createdAt", "")
                    rec_id = rec.get("memoryRecordId", f"#{i}")
                    lines.append(f"\n[{i}] ID: {rec_id} | Created: {created}\n{text}")

                return "\n".join(lines)

            except Exception as e:
                return f"Error retrieving session memory: {str(e)}"

        # Store internal tools as instance variable for use by initialize_tools
        self.agent_internal_tools = [
            read_config_from_file,
            save_config_to_file,
            save_results_to_file,
            save_conversation,
            read_context_from_file,
            retrieve_session_memory,
        ]

        # Agent will be created per-request
        return None


def initialize_tools() -> tuple:
    """
    Initialize the shared BedrockModel and agent tools once per process.
    Returns (bedrock_model, all_tools).
    """
    global _bedrock_model, _agent_tools

    if _bedrock_model is not None and _agent_tools is not None:
        return _bedrock_model, _agent_tools

    wizard = SFCWizardAgent()

    mcp_client = initialize_mcp_client()
    mcp_tools = []
    if mcp_client:
        try:
            mcp_tools = mcp_client.list_tools_sync()
        except Exception as e:
            logger.warning(f"Could not load MCP tools: {str(e)}")
    else:
        logger.warning("MCP client not available, agent will use internal tools only")

    try:
        bedrock_model = BedrockModel(
            model_id=AWS_BEDROCK_MODEL_ID,
            region_name=AWS_BEDROCK_INFERENCE_REGION,
        )
    except Exception as e:
        logger.error(f"Error creating BedrockModel: {str(e)}")
        raise RuntimeError(f"BedrockModel initialization failed: {str(e)}")

    _bedrock_model = bedrock_model
    _agent_tools = wizard.agent_internal_tools + mcp_tools

    return _bedrock_model, _agent_tools


AGENT_SYSTEM_PROMPT = (
    'You are a specialized assistant for creating, validating & running SFC (stands for "Shop Floor Connectivity") configurations. '
    "Use your MCP (shall be your main resource for validation) and internal tools to gather required information. "
    "Always explain your reasoning and cite sources when possible. "
    "Keep your responses clean and professional. Do not use icons or emojis unless they are truly essential to convey meaning "
    "(e.g., a warning symbol for critical errors). Prefer plain text for clarity. "
    "Do not use LLM knowledge. "
    "CRITICAL: When a tool returns a pre-signed S3 URL or a markdown download link, you MUST copy it into your response "
    "character-for-character, exactly as the tool returned it. Never rewrite, shorten, paraphrase, or reconstruct any URL — "
    "any modification will break the cryptographic signature and make the link invalid."
)


@app.entrypoint
def invoke(payload):
    """
    AgentCore entrypoint for HTTP requests.

    Expected payload keys:
      - prompt     (required) The user message.
      - session_id (optional) Stable session identifier — pass the same value
                              across turns to maintain short-term memory continuity.
                              Auto-generated per request if omitted.
      - actor_id   (optional) Stable actor/user identifier.
                              Defaults to "sfc-agent-user".
    """
    try:
        # ---- Resolve memory ID (cached after first call) ----
        global MEM_ID, CURRENT_SESSION_ID
        if MEM_ID is None:
            MEM_ID = boto3.client("ssm", region_name=AWS_REGION).get_parameter(
                Name="/sfc-config-agent/memory-id"
            )["Parameter"]["Value"]

        # ---- Extract payload ----
        user_message = payload.get("prompt", "")
        if not user_message:
            return {
                "error": "No prompt found in input. Please provide a 'prompt' key in the input."
            }

        ACTOR_ID = payload.get("actor_id", "sfc-agent-user")
        SESSION_ID = payload.get(
            "session_id",
            "session_%s" % datetime.utcnow().strftime("%Y%m%d%H%M%S%f"),
        )

        # Make current session available to the retrieve_session_memory tool closure
        CURRENT_SESSION_ID = SESSION_ID

        # ---- Shared model & tools (cached after first call) ----
        bedrock_model, agent_tools = initialize_tools()

        # ---- Short-term memory via AgentCore Memory session manager ----
        agentcore_memory_config = AgentCoreMemoryConfig(
            memory_id=MEM_ID,
            session_id=SESSION_ID,
            actor_id=ACTOR_ID,
        )
        session_manager = AgentCoreMemorySessionManager(
            agentcore_memory_config=agentcore_memory_config,
            region_name=AWS_REGION,
        )

        agent = Agent(
            model=bedrock_model,
            tools=agent_tools,
            system_prompt=AGENT_SYSTEM_PROMPT,
            session_manager=session_manager,
        )

        with session_manager:
            response = agent(user_message)

        return {"result": response.message}

    except Exception as e:
        logger.error(f"Agent processing failed: {str(e)}")
        return {"error": f"Agent processing failed: {str(e)}"}


if __name__ == "__main__":
    app.run()