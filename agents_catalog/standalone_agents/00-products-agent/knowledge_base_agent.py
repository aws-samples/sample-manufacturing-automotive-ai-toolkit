#!/usr/bin/env python3
"""
Knowledge Base Agent using Strands framework

This Strands agent provides information from company documentation and knowledge base.
"""

from strands import Agent
from strands_tools import think, file_read, file_write

AGENT_PROMPT = """
You are a Knowledge Base Assistant that provides accurate information from company documentation and resources.
You help users find answers to their questions by retrieving and explaining information from the knowledge base.

Core Capabilities:
- Answer questions about product specifications and features
- Provide troubleshooting guidance and technical support
- Explain company policies, procedures, and guidelines
- Share best practices and recommendations
- Direct users to relevant documentation and resources

When users ask about product specifications, provide detailed technical information.
When users need troubleshooting help, offer step-by-step guidance to resolve their issues.
When users inquire about policies or procedures, explain them clearly and accurately.

Always cite your sources when providing information and acknowledge when you don't have the answer.
Focus on providing accurate, helpful information in a clear and concise manner.
"""

# Create the Strands agent
agent = Agent(
    system_prompt=AGENT_PROMPT,
    tools=[think, file_read]
)

# Integrate with Bedrock AgentCore
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload, context):
    """Handler for agent invocation"""
    user_message = payload.get("prompt", "No prompt found in input, please guide customer to create a json payload with prompt key")
    
    # Pass the message to the agent
    result = agent(user_message)
    
    # For demonstration, we'll add some sample source information
    if "product specs" in user_message.lower():
        source = "product_catalog.pdf"
        confidence = 0.92
    elif "troubleshooting" in user_message.lower():
        source = "support_guide.pdf"
        confidence = 0.87
    elif "warranty" in user_message.lower():
        source = "warranty_terms.pdf"
        confidence = 0.95
    else:
        source = None
        confidence = 0
    
    return {
        "result": result.message,
        "source": source,
        "confidence": confidence
    }

if __name__ == "__main__":
    app.run()
