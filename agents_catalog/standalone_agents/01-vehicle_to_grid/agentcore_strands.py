from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters

app = BedrockAgentCoreApp()

AGENT_PROMPT = """
You are a Vehicle-to-Grid (V2G) Optimization Agent that helps users maximize
value from their electric vehicles through grid integration.

Core Capabilities:
- Monitor energy market prices and grid load data
- Create optimized charging/discharging schedules
- Provide utility rate information by location
- Recommend optimal times for grid participation
- Calculate potential savings from V2G activities
"""

# Initialize the MCP client
v2g_mcp_server = MCPClient(lambda: stdio_client(StdioServerParameters(command="python", args=["v2g_mcp_server.py"])))

@app.entrypoint
def invoke(payload):
    """V2G optimization agent entrypoint"""
    user_message = payload.get("prompt", "How can I help optimize your EV charging?")
    
    # Start the MCP client session and create agent
    with v2g_mcp_server:
        tool_list = v2g_mcp_server.list_tools_sync()
        agent = Agent(
            system_prompt=AGENT_PROMPT,
            tools=tool_list
        )
        result = agent(user_message)
        return {"result": result.message}

if __name__ == "__main__":
    app.run()
