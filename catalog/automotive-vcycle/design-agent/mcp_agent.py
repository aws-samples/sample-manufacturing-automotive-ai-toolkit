import os
import time
import json
import asyncio
import requests
from typing import Dict, Any, Optional

from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore import BedrockAgentCoreApp
from boto3.session import Session


GATEWAY_URL = os.getenv("GATEWAY_URL")
GATEWAY_CLIENT_ID = os.getenv("GATEWAY_CLIENT_ID")
GATEWAY_CLIENT_SECRET = os.getenv("GATEWAY_CLIENT_SECRET")
RESOURCE_SERVER_ID = os.getenv("RESOURCE_SERVER_ID")
GATEWAY_USER_POOL_ID = os.getenv("GATEWAY_USER_POOL_ID")

boto_session = Session()
REGION = boto_session.region_name

# Initialize the AgentCore Runtime application
# This wrapper makes our agent deployable to AgentCore
app = BedrockAgentCoreApp()

model_id = "us.amazon.nova-2-lite-v1:0" #"us.anthropic.claude-haiku-4-5-20251001-v1:0"
model = BedrockModel(
    model_id=model_id, max_tokens=40000
)

def get_token(user_pool_id: str, client_id: str, client_secret: str, scope_string: str, REGION: str) -> dict:
    try:
        user_pool_id_without_underscore = user_pool_id.replace("_", "")
        url = f"https://{user_pool_id_without_underscore}.auth.{REGION}.amazoncognito.com/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope_string,

        }
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as err:
        return {"error": str(err)}


scopeString=f"{RESOURCE_SERVER_ID}/gateway:read {RESOURCE_SERVER_ID}/gateway:write"
token_response = get_token(GATEWAY_USER_POOL_ID, GATEWAY_CLIENT_ID, GATEWAY_CLIENT_SECRET,scopeString,REGION)
token = token_response["access_token"]
print("Token response:", token)

def create_streamable_http_transport():
    return streamablehttp_client(GATEWAY_URL,headers={"Authorization": f"Bearer {token}"})

client = MCPClient(create_streamable_http_transport)
client.start()
gateway_tools=client.list_tools_sync()

design_agent = Agent(
    name="design_generator",
    model=model,
    tools=gateway_tools,
    system_prompt="""You are an automotive software architect specializing in vehicle infotainment and systems implemented in Kotlin programming language.

Generate comprehensive technical design documents from validated business requirements document (BRD), software requirements document (SRD) and other supplementary documents if they exist.

In your technical design document ALWAYS include:

- **Architecture Overview**: High-level system architecture with component diagram
- **Component Specifications**: Detailed specifications for each component
- **Interface Definitions**: APIs, protocols, and data contracts
- **Data Models**: Entity relationships, schemas, and constraints
- **Safety Considerations**: ISO 26262 compliance and risk mitigation
- **Implementation Guidance**: Step-by-step development approach
- **Error Handling**: Error scenarios and recovery strategies
- **Testing Strategy**: Test approach and coverage plan

Focus on modularity, and testability."""
)

# AgentCore entrypoint
@app.entrypoint
def automotive_design_generator(payload):

    start_time = time.time()
    try:
        # Extract documents from payload
        srs_documents = payload.get("srs_documents")
        brd_documents = payload.get("brd_documents")
        other_documents = payload.get("other_documents", "")

        # Validate mandatory inputs
        if not srs_documents:
            error_response = {
                "error": "No SRS documents provided",
                "message": "The 'srs_documents' field is required in the payload"
            }
            print(f"[ERROR] {error_response['error']}")
            return error_response

        if not brd_documents:
            error_response = {
                "error": "No BRD documents provided",
                "message": "The 'brd_documents' field is required in the payload"
            }
            print(f"[ERROR] {error_response['error']}")
            return error_response

        prompt = f"""Generate a comprehensive technical design document from the following validated requirements:

## Software Requirements Specification (SRS):
{srs_documents}

## Business Requirements Document (BRD):
{brd_documents}"""

        if other_documents.strip():
            prompt += f"""

## Additional Supporting Documents:
{other_documents}"""

        prompt += """

IMPORTANT: Before generating the design, retrieve and incorporate relevant design guidelines using the available tools. This will ensure your design follows established automotive standards and best practices.

Generate a complete technical design document that covers all required sections. NEVER include code in the technical design."""

        print("[INFO] Executing design agent...")

        # Execute agent using async invoke
        import asyncio
        #result = asyncio.run(design_agent.invoke_async(prompt))
        result = design_agent(prompt)

        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        print(f"[INFO] Agent execution completed in {execution_time_ms}ms")

        # Extract result text
        design_text = str(result)

        # Build response
        response = {
            "execution_time_ms": execution_time_ms,
            "step1_design_generation": {
                "design": design_text,
                "completeness_analysis": "Design generated successfully"
            },
            "step2_design_validation": {
                "validated": False,
                "reason": "Simplified version - validation not implemented"
            }
        }

        print("[INFO] automotive_design_generator completed successfully")
        return response

    except Exception as e:
        # Error handling
        execution_time_ms = int((time.time() - start_time) * 1000)
        error_response = {
            "error": "Design generation failed",
            "message": str(e),
            "execution_time_ms": execution_time_ms
        }
        print(f"[ERROR] Design generation failed: {e}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return error_response

if __name__ == "__main__":
    app.run()
