"""
Communication Agent - ERP integration and notification coordinator
Ready for Amazon Bedrock AgentCore deployment
"""
import os
os.environ["BYPASS_TOOL_CONSENT"]="true"

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
import json
import boto3
from model_config import get_model_id

# Initialize AgentCore App
app = BedrockAgentCoreApp()

@app.entrypoint
def handler(event):
    """AgentCore entrypoint for Communication Agent"""
    try:
        # Extract prompt from event
        prompt = event.get("prompt", "")
        
        # Process with communication agent
        result = communication_agent(prompt)
        
        return {
            "statusCode": 200,
            "body": {
                "agent_type": "communication",
                "result": result,
                "success": True
            }
        }
    except Exception as e:
        # Log the error for debugging
        print(f"Communication Agent error: {str(e)}")
        return {
            "statusCode": 500,
            "body": {
                "agent_type": "communication",
                "error": str(e),
                "success": False
            }
        }

# Initialize the Communication Agent
model_id = get_model_id()
current_region = boto3.Session().region_name
bedrock_model = BedrockModel(
    model_id=model_id,
    temperature=0.1,
    region_name=current_region
)

@tool
def send_quality_alert(message: str, defect_type: str = "general") -> str:
    """Send SNS notification for quality issues"""
    try:
        sns_client = boto3.client('sns')
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
        region = boto3.Session().region_name or 'us-east-1'
        topic_arn = f"arn:aws:sns:{region}:{account_id}:quality-inspection-alerts"
        
        sns_client.publish(
            TopicArn=topic_arn,
            Message=message,
            Subject=f"Quality Inspection Alert - {defect_type.title()} Detected"
        )
        return f"SNS notification sent successfully for {defect_type}"
    except Exception as e:
        return f"SNS notification failed: {str(e)}"

communication_agent = Agent(
    model=bedrock_model,
    system_prompt="""You are a communication coordinator. Handle notifications and ERP updates based on defect results.

When defects are found, ALWAYS use the send_quality_alert tool to notify stakeholders.

ACTIONS:
- Defects found: Use send_quality_alert tool, update ERP with defect record
- No defects: Update ERP with pass record, continue production notifications
- Critical defects: Use send_quality_alert tool with urgent message

Return JSON format:
{
  "notifications_sent": [{"recipient": "quality_team", "type": "defect_alert", "urgency": "high"}],
  "erp_updates": [{"system": "SAP_QM", "record_type": "inspection_result", "status": "updated"}],
  "escalations": [{"level": "supervisor", "reason": "critical_defect", "sent": true}]
}""",
    tools=[send_quality_alert]
)

class CommunicationAgent:
    """Agent responsible for system integration and notifications"""
    
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
        """Get the system prompt for the Communication Agent"""
        return """You are a communication coordinator. Handle notifications and ERP updates based on defect results.

ACTIONS:
- Defects found: Alert quality team, update ERP with defect record
- No defects: Update ERP with pass record, continue production notifications
- Critical defects: Immediate escalation to supervisors

Return JSON format:
{
  "notifications_sent": [{"recipient": "quality_team", "type": "defect_alert", "urgency": "high"}],
  "erp_updates": [{"system": "SAP_QM", "record_type": "inspection_result", "status": "updated"}],
  "escalations": [{"level": "supervisor", "reason": "critical_defect", "sent": true}]
}"""
    
    def handle_communications(self, action_results, sop_decision, vision_results):
        """Handle all communication tasks based on workflow results"""
        combined_input = f"Action Results: {action_results}\nSOP Decision: {sop_decision}\nVision Results: {vision_results}"
        result = self.agent(combined_input)
        
        # Send SNS notification if defects found
        try:
            sns_client = boto3.client('sns')
            sts = boto3.client('sts')
            account_id = sts.get_caller_identity()['Account']
            region = boto3.Session().region_name or 'us-east-1'
            topic_arn = f"arn:aws:sns:{region}:{account_id}:quality-inspection-alerts"
            
            if "defect" in str(vision_results).lower() or "reject" in str(sop_decision).lower():
                message = f"Quality Inspection Alert\n\nVision Results: {vision_results}\nSOP Decision: {sop_decision}\nAction Results: {action_results}"
                sns_client.publish(
                    TopicArn=topic_arn,
                    Message=message,
                    Subject="Quality Inspection Alert - Defects Detected"
                )
        except Exception as e:
            print(f"SNS publish error: {e}")
        
        return result
    
    def __call__(self, input_data):
        """Make the agent callable"""
        return self.agent(input_data)

if __name__ == "__main__":
    app.run()