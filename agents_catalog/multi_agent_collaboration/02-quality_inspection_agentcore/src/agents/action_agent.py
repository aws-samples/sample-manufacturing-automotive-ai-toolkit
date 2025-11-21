"""
Action Agent - Physical action controller for manufacturing operations
Ready for Amazon Bedrock AgentCore deployment
"""
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
import json
from model_config import get_model_id

# Initialize AgentCore App
app = BedrockAgentCoreApp()

@app.entrypoint
def handler(event):
    """AgentCore entrypoint for Action Agent"""
    try:
        # Extract prompt from event
        prompt = event.get("prompt", "")
        
        # Process with action agent
        result = action_agent(prompt)
        
        return {
            "statusCode": 200,
            "body": {
                "agent_type": "action",
                "result": result,
                "success": True
            }
        }
    except Exception as e:
        # Log the error for debugging
        print(f"Action Agent error: {str(e)}")
        return {
            "statusCode": 500,
            "body": {
                "agent_type": "action",
                "error": str(e),
                "success": False
            }
        }

# Initialize the Action Agent
model_id = get_model_id()
bedrock_model = BedrockModel(
    model_id=model_id,
    temperature=0.1,
)

action_agent = Agent(
    model=bedrock_model,
    system_prompt="""You are a physical action controller. Execute actions based on defect analysis.

ACTIONS:
- Defects found: File to defects folder, generate report
- No defects: File to processed folder, continue production
- Rework needed: Schedule repair operations
- Scrap required: Remove from production line

Return JSON format:
{
  "physical_action": "file_defective" or "file_processed" or "schedule_rework" or "remove_scrap",
  "file_location": "defects/" or "processedimages/",
  "report_generated": true or false,
  "production_impact": "description"
}"""
)

class ActionAgent:
    """Agent responsible for executing physical manufacturing actions"""
    
    def __init__(self, model_id=None, temperature=0.1):
        if model_id is None:
            model_id = get_model_id()
        self.bedrock_model = BedrockModel(
            model_id=model_id,
            temperature=temperature,
        )
        
        self.agent = Agent(
            model=self.bedrock_model,
            system_prompt=self._get_system_prompt()
        )
    
    def _get_system_prompt(self):
        """Get the system prompt for the Action Agent"""
        return """You are a physical action controller. Execute actions based on defect analysis.

ACTIONS:
- Defects found: File to defects folder, generate report
- No defects: File to processed folder, continue production
- Rework needed: Schedule repair operations
- Scrap required: Remove from production line

Return JSON format:
{
  "physical_action": "file_defective" or "file_processed" or "schedule_rework" or "remove_scrap",
  "file_location": "defects/" or "processedimages/",
  "report_generated": true or false,
  "production_impact": "description"
}"""
    
    def execute_action(self, sop_decision, vision_results):
        """Execute physical actions based on SOP decision and vision results"""
        combined_input = f"SOP Decision: {sop_decision}\nVision Results: {vision_results}"
        return self.agent(combined_input)
    
    def __call__(self, input_data):
        """Make the agent callable"""
        return self.agent(input_data)

if __name__ == "__main__":
    app.run()