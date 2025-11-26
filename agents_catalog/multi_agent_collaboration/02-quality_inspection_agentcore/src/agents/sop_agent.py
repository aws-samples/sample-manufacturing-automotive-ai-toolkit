"""
SOP Agent - Standard Operating Procedure compliance and quality rules
Ready for Amazon Bedrock AgentCore deployment
"""
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
import json
import boto3
from model_config import get_model_id

# Initialize AgentCore App
app = BedrockAgentCoreApp()

@app.entrypoint
def handler(event):
    """AgentCore entrypoint for SOP Agent"""
    try:
        # Extract prompt from event
        prompt = event.get("prompt", "")
        
        # Process with SOP agent
        result = sop_agent(prompt)
        
        return {
            "statusCode": 200,
            "body": {
                "agent_type": "sop",
                "result": result,
                "success": True
            }
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": {
                "agent_type": "sop",
                "error": str(e),
                "success": False
            }
        }

# Initialize the SOP Agent
model_id = get_model_id()
current_region = boto3.Session().region_name
bedrock_model = BedrockModel(
    model_id=model_id,
    temperature=0.1,
    region_name=current_region
)

sop_agent = Agent(
    model=bedrock_model,
    system_prompt="""You are a SOP compliance specialist. Apply quality rules based on defect analysis.

RULES:
- Scratches ≥5mm: REWORK (SOP-SCR-001)
- Any Crack: SCRAP (SOP-CRK-001) 
- Scratches <5mm: ACCEPT with monitoring (SOP-SCR-002)
- No defects: ACCEPT (SOP-GEN-001)

Analyze the vision results and determine appropriate action.
Return JSON format:
{
  "disposition": "accept" or "rework" or "scrap",
  "sop_rule": "rule_id", 
  "action_required": "specific action",
  "reasoning": "detailed explanation"
}"""
)

class SOPAgent:
    """Agent responsible for applying SOP rules and compliance decisions"""
    
    def __init__(self, model_id=None, temperature=0.1):
        if model_id is None:
            model_id = get_model_id()
        current_region = boto3.Session().region_name
        self.bedrock_model = BedrockModel(
            model_id=model_id,
            temperature=temperature,
            region_name=current_region
        )
        
        self.agent = Agent(
            model=self.bedrock_model,
            system_prompt=self._get_system_prompt()
        )
    
    def _get_system_prompt(self):
        """Get the system prompt for the SOP Agent"""
        return """You are a SOP compliance specialist. Apply quality rules based on defect analysis.

RULES:
- Scratches ≥5mm: REWORK (SOP-SCR-001)
- Any Crack: SCRAP (SOP-CRK-001) 
- Scratches <5mm: ACCEPT with monitoring (SOP-SCR-002)
- No defects: ACCEPT (SOP-GEN-001)

Analyze the vision results and determine appropriate action.
Return JSON format:
{
  "disposition": "accept" or "rework" or "scrap",
  "sop_rule": "rule_id", 
  "action_required": "specific action",
  "reasoning": "detailed explanation"
}"""
    
    def evaluate_compliance(self, vision_results):
        """Evaluate SOP compliance based on vision results"""
        return self.agent(vision_results)
    
    def __call__(self, input_data):
        """Make the agent callable"""
        return self.evaluate_compliance(input_data)

if __name__ == "__main__":
    app.run()