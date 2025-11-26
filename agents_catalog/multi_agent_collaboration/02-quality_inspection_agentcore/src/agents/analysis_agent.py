"""
Analysis Agent - Quality trend analysis and predictive analytics
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
    """AgentCore entrypoint for Analysis Agent"""
    try:
        # Extract prompt from event
        prompt = event.get("prompt", "")
        
        # Process with analysis agent
        result = analysis_agent(prompt)
        
        return {
            "statusCode": 200,
            "body": {
                "agent_type": "analysis",
                "result": result,
                "success": True
            }
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": {
                "agent_type": "analysis",
                "error": str(e),
                "success": False
            }
        }

# Initialize the Analysis Agent
model_id = get_model_id()
current_region = boto3.Session().region_name
bedrock_model = BedrockModel(
    model_id=model_id,
    temperature=0.1,
    region_name=current_region
)

analysis_agent = Agent(
    model=bedrock_model,
    system_prompt="""You are a quality trend analyst. Analyze defect patterns and production metrics.

ANALYSIS TASKS:
- Calculate defect rates and quality scores
- Identify defect type patterns (scratches vs cracks)
- Predict maintenance needs based on defect frequency
- Generate improvement recommendations

Return JSON format:
{
  "quality_score": number,
  "defect_rate_trend": "increasing" or "decreasing" or "stable",
  "common_defect_types": ["scratch", "crack"],
  "maintenance_prediction": "schedule_inspection" or "continue_normal",
  "recommendations": ["specific_actions"]
}"""
)

class AnalysisAgent:
    """Agent responsible for quality analytics and trend analysis"""
    
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
        """Get the system prompt for the Analysis Agent"""
        return """You are a quality trend analyst. Analyze defect patterns and production metrics.

ANALYSIS TASKS:
- Calculate defect rates and quality scores
- Identify defect type patterns (scratches vs cracks)
- Predict maintenance needs based on defect frequency
- Generate improvement recommendations

Return JSON format:
{
  "quality_score": number,
  "defect_rate_trend": "increasing" or "decreasing" or "stable",
  "common_defect_types": ["scratch", "crack"],
  "maintenance_prediction": "schedule_inspection" or "continue_normal",
  "recommendations": ["specific_actions"]
}"""
    
    def analyze_trends(self, complete_workflow_results):
        """Analyze quality trends from complete workflow data"""
        return self.agent(complete_workflow_results)
    
    def __call__(self, input_data):
        """Make the agent callable"""
        return self.analyze_trends(input_data)

if __name__ == "__main__":
    app.run()