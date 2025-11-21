#!/usr/bin/env python3
"""
Quality Inspection Orchestrator Agent - Routes inspection tasks to specialized agents.
"""

import os
import boto3
import json
import time
from strands import Agent, tool
from strands.models import BedrockModel
from model_config import get_model_id



# AgentCore compatibility
try:
    from bedrock_agentcore.runtime import BedrockAgentCoreApp
    app = BedrockAgentCoreApp()
except ImportError:
    app = None

# AgentCore entrypoint
if app:
    @app.entrypoint
    def handler(event):
        """AgentCore entrypoint for orchestrator requests."""
        prompt = event.get("prompt", "")
        if not prompt:
            return {"error": "No prompt provided"}
        
        try:
            # Create orchestrator agent with proper tools
            model_id = get_model_id()
            nova_model = BedrockModel(model_id=model_id)
            
            orchestrator = Agent(
                system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
                model=nova_model,
                tools=[execute_full_workflow, visual_inspection_service, move_processed_file]
            )
            
            # Let the agent decide which tool to use based on the prompt
            response = orchestrator(prompt)
            return {"response": str(response)}
        except Exception as e:
            return {"error": f"Processing error: {str(e)}"}

# System prompt for the orchestrator
ORCHESTRATOR_SYSTEM_PROMPT = """
You are a quality inspection orchestrator. You MUST ALWAYS use the execute_full_workflow tool for ANY inspection request.

When you receive ANY request mentioning an image path or quality inspection:
1. IMMEDIATELY call execute_full_workflow with the image path
2. Return ONLY the tool result
3. NEVER generate mock data or simulated responses

If no image path is provided, ask for one. If an image path is provided, use the tool immediately.

You have ONE job: call execute_full_workflow(image_path="...") for every inspection request.
"""


@tool
def visual_inspection_service(image_path: str, part_specification: str = "") -> str:
    """
    Route visual inspection requests to the visual inspection agent.
    
    Args:
        image_path: Path to the image file for inspection
        part_specification: Optional part specification details
        
    Returns:
        Visual inspection analysis results
    """
    if app:
        # AgentCore mode - invoke visual inspection agent
        try:
            import uuid
            agentcore_client = boto3.client('bedrock-agentcore')
            
            # Get reference image S3 URI from Parameter Store
            ssm = boto3.client('ssm')
            try:
                ref_param = ssm.get_parameter(Name='/quality-inspection/reference-image-s3-uri')
                reference_s3_url = ref_param['Parameter']['Value']
            except Exception as e:
                return f'{{"defect_detected": "U", "analysis_summary": "Configuration error: Reference image parameter not found - {str(e)}", "confidence": 0, "defects": []}}'
            
            # Create payload matching vision agent's expected format
            payload = json.dumps({
                "prompt": f"Analyze these images for defects: Reference={reference_s3_url}, Test={image_path}",
                "reference_s3_url": reference_s3_url,
                "test_s3_url": image_path
            }).encode()
            
            # Use a fresh session ID to avoid conversation state corruption
            session_id = f"vision-{uuid.uuid4().hex}-{int(time.time())}"
            
            # Get vision agent ARN from Parameter Store
            try:
                vision_param = ssm.get_parameter(Name='/quality-inspection/agentcore-runtime/vision')
                vision_arn = vision_param['Parameter']['Value']
            except Exception as e:
                return f'{{"defect_detected": "U", "analysis_summary": "Vision agent ARN not found in Parameter Store: {str(e)}", "confidence": 0, "defects": []}}'
            response = agentcore_client.invoke_agent_runtime(
                agentRuntimeArn=vision_arn,
                runtimeSessionId=session_id,
                payload=payload
            )
            # Parse AgentCore response properly - use 'response' not 'payload'
            if 'response' in response:
                # Read the streaming response
                response_content = ""
                for chunk in response['response']:
                    response_content += chunk.decode('utf-8')
                
                # Parse the JSON response
                if response_content:
                    try:
                        payload_data = json.loads(response_content)
                        
                        # Extract the result from the AgentCore response format
                        if 'body' in payload_data and 'result' in payload_data['body']:
                            result = payload_data['body']['result']
                            return result
                        else:
                            return json.dumps(payload_data)
                    except json.JSONDecodeError as e:
                        return f'{{"defect_detected": "U", "analysis_summary": "Response parsing error: {str(e)}", "confidence": 0, "defects": []}}'
                else:
                    return '{"defect_detected": "U", "analysis_summary": "Empty response from vision agent", "confidence": 0, "defects": []}'
            else:
                return '{"defect_detected": "U", "analysis_summary": "No response from vision agent", "confidence": 0, "defects": []}'
            
        except Exception as e:
            error_msg = str(e)
            return f'{{"defect_detected": "U", "analysis_summary": "Vision agent error: {error_msg[:200]}", "confidence": 0, "defects": []}}'
    else:
        return "AgentCore not available - cannot perform visual inspection"


@tool
def store_inspection_results(inspection_data: dict) -> str:
    """
    Store inspection results in DynamoDB.
    
    Args:
        inspection_data: Dictionary containing inspection results
        
    Returns:
        Storage confirmation message
    """
    try:
        import boto3
        from datetime import datetime
        import uuid
        
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('vision-inspection-data')
        
        inspection_id = f"INS_{uuid.uuid4().hex[:8]}"
        timestamp = datetime.utcnow().isoformat()
        
        # Extract filename from image path
        image_path = inspection_data.get('image_path', '')
        filename = image_path.split('/')[-1] if image_path else 'unknown'
        
        item = {
            'inspection_id': inspection_id,
            'image_key': image_path,
            'filename': filename,
            'timestamp': timestamp,
            'status': 'completed',
            'defect_detected': inspection_data.get('defect_detected', 'U'),
            'analysis_summary': inspection_data.get('analysis_summary', ''),
            'confidence': inspection_data.get('confidence', 0),
            'recommendation': inspection_data.get('recommendation', 'REVIEW'),
            'model_used': 'agentcore-v1.0'
        }
        
        # Store defects array with proper structure
        if 'defects' in inspection_data and inspection_data['defects']:
            # Store as DynamoDB List for native querying
            item['defects'] = inspection_data['defects']
            # Also store as JSON string for compatibility
            item['defect_details'] = json.dumps(inspection_data['defects'])
        else:
            item['defects'] = []
        
        # Store clean analysis summary from structured JSON
        item['analysis_summary'] = inspection_data.get('analysis_summary', f"Defects: {inspection_data.get('defect_detected', 'U')}, Confidence: {inspection_data.get('confidence', 0)}%")
        
        table.put_item(Item=item)
        return f"Stored inspection results: {inspection_id}"
        
    except Exception as e:
        return f"Error storing results: {str(e)}"

@tool
def move_processed_file(image_path: str, defect_detected: str, defects: list = None) -> str:
    """
    Move processed file to appropriate S3 folder based on inspection results.
    
    Args:
        image_path: S3 path to the image
        defect_detected: Y/N indicating if defects were found
        defects: List of defect details (optional)
        
    Returns:
        File operation result message
    """
    try:
        import boto3
        import json
        
        # Parse S3 path
        if image_path.startswith('s3://'):
            path_parts = image_path[5:].split('/', 1)
            bucket = path_parts[0]
            key = path_parts[1]
        else:
            return f"Invalid S3 path: {image_path}"
        
        s3 = boto3.client('s3')
        filename = key.split('/')[-1]
        
        if defect_detected == 'Y':
            # Move to defects folder
            new_key = f"defects/{filename}"
            
            # Create JSON file with defect details if available
            if defects:
                json_key = f"defects/{filename.rsplit('.', 1)[0]}.json"
                json_content = json.dumps(defects, indent=2)
                s3.put_object(
                    Bucket=bucket,
                    Key=json_key,
                    Body=json_content,
                    ContentType='application/json'
                )
        else:
            # Move to processedimages folder
            new_key = f"processedimages/{filename}"
        
        # Copy to new location
        s3.copy_object(
            Bucket=bucket,
            CopySource={'Bucket': bucket, 'Key': key},
            Key=new_key
        )
        
        # Delete original
        s3.delete_object(Bucket=bucket, Key=key)
        
        return f"File moved from {key} to {new_key}"
        
    except Exception as e:
        return f"Error moving file: {str(e)}"



def invoke_agentcore_agent(agent_name_pattern: str, prompt: str, agent_name: str) -> str:
    """Helper function to invoke AgentCore agents using SSM parameter ARNs"""
    try:
        import uuid
        
        agentcore_client = boto3.client('bedrock-agentcore')
        ssm = boto3.client('ssm')
        
        # Map agent patterns to SSM parameter names
        param_mapping = {
            "quality_inspection_analysis": "/quality-inspection/agentcore-runtime/analysis",
            "quality_inspection_sop": "/quality-inspection/agentcore-runtime/sop",
            "quality_inspection_action": "/quality-inspection/agentcore-runtime/action",
            "quality_inspection_communication": "/quality-inspection/agentcore-runtime/communication"
        }
        
        param_name = param_mapping.get(agent_name_pattern)
        if not param_name:
            return f'{{"error": "Unknown agent pattern: {agent_name_pattern}"}}'
        
        # Get agent ARN from Parameter Store
        try:
            param = ssm.get_parameter(Name=param_name)
            agent_arn = param['Parameter']['Value']
        except Exception as e:
            return f'{{"error": "Agent ARN not found in Parameter Store {param_name}: {str(e)}"}}'
        
        payload = json.dumps({"prompt": prompt}).encode()
        session_id = f"{agent_name}-{uuid.uuid4().hex}-{int(time.time())}"
        
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=session_id,
            payload=payload
        )
        
        # Parse AgentCore response properly - use 'response' not 'payload'
        if 'response' in response:
            response_content = ""
            for chunk in response['response']:
                response_content += chunk.decode('utf-8')
            
            if response_content:
                try:
                    payload_data = json.loads(response_content)
                    return json.dumps(payload_data)
                except json.JSONDecodeError:
                    return f'{{"error": "JSON decode error for {agent_name} agent"}}'
            else:
                return f'{{"error": "Empty response from {agent_name} agent"}}'
        else:
            return f'{{"error": "No response from {agent_name} agent"}}'
        
    except Exception as e:
        return f'{{"error": "{agent_name} agent error: {str(e)}"}}'

def parse_agent_response(response: str, agent_type: str) -> dict:
    """Parse agent response to extract structured data"""
    import json
    import re
    
    # Handle string responses first
    if not isinstance(response, str):
        response = str(response)
    
    try:
        # Parse the outer JSON response
        parsed_response = json.loads(response)
        
        # Handle AgentCore response format with statusCode and body
        if isinstance(parsed_response, dict) and 'statusCode' in parsed_response:
            if 'body' in parsed_response and isinstance(parsed_response['body'], dict):
                body = parsed_response['body']
                if 'result' in body:
                    # The result is a JSON string that needs to be parsed
                    result_str = body['result']
                    try:
                        # First try to parse as JSON directly
                        parsed = json.loads(result_str)
                        return parsed
                    except json.JSONDecodeError:
                        # Extract JSON from conversational text
                        json_match = re.search(r'\{[\s\S]*?\}', result_str)
                        if json_match:
                            try:
                                return json.loads(json_match.group(0))
                            except json.JSONDecodeError:
                                pass
                        # If all parsing fails, return the string as analysis_summary
                        return {'analysis_summary': result_str, 'defect_detected': 'U', 'confidence': 0, 'defects': []}
        
        # Handle simple response format
        if isinstance(parsed_response, dict) and 'response' in parsed_response:
            inner_response = parsed_response['response']
            # Try to parse the inner response as JSON
            try:
                return json.loads(inner_response)
            except json.JSONDecodeError:
                # Extract JSON from conversational text
                json_match = re.search(r'\{[\s\S]*?\}', inner_response)
                if json_match:
                    return json.loads(json_match.group(0))
        
        # If it's already a dict, return it
        if isinstance(parsed_response, dict):
            return parsed_response
        
        # Try direct JSON parsing as fallback
        return json.loads(response)
        
    except Exception as e:
        # Return default structure based on agent type
        if agent_type == "vision":
            return {
                'defect_detected': 'U',
                'analysis_summary': 'Parsing error - manual review required',
                'confidence': 0,
                'defects': []
            }
        elif agent_type == "analysis":
            return {
                'quality_score': 0,
                'defect_rate_trend': 'unknown',
                'maintenance_prediction': 'review_required'
            }
        elif agent_type == "sop":
            return {
                'disposition': 'review',
                'sop_rule': 'SOP-ERR-001',
                'action_required': 'manual_review'
            }
        elif agent_type == "action":
            return {
                'physical_action': 'hold_for_review',
                'file_location': 'review/',
                'production_impact': 'minimal'
            }
        elif agent_type == "communication":
            return {
                'notifications_sent': [],
                'erp_updates': [],
                'escalations': []
            }
        
        return {}

@tool
def execute_full_workflow(image_path: str, part_specification: str = "") -> str:
    """
    Execute the complete quality inspection workflow with all 5 agents.
    
    Workflow: Vision → Analysis → SOP → Action → Communication
    
    Args:
        image_path: Path to the image file for inspection
        part_specification: Optional part specification details
        
    Returns:
        Complete workflow results from all agents
    """
    try:
        # Step 1: Vision Agent
        visual_results = visual_inspection_service(image_path, part_specification)
        
        # visual_inspection_service already returns clean JSON, just parse it directly
        try:
            vision_data = json.loads(visual_results)
        except json.JSONDecodeError:
            # Fallback to parse_agent_response if it's not clean JSON
            vision_data = parse_agent_response(visual_results, "vision")
        
        # Step 2: Analysis Agent - Quality trend analysis
        analysis_prompt = f"Analyze: {json.dumps(vision_data)}"
        analysis_results = invoke_agentcore_agent(
            "quality_inspection_analysis",
            analysis_prompt,
            "analysis"
        )
        analysis_data = parse_agent_response(analysis_results, "analysis")
        
        # Step 3: SOP Agent - Compliance decisions
        sop_prompt = f"SOP decision: {json.dumps(vision_data)}"
        sop_results = invoke_agentcore_agent(
            "quality_inspection_sop",
            sop_prompt,
            "sop"
        )
        sop_data = parse_agent_response(sop_results, "sop")
        
        # Step 4: Action Agent - Physical actions
        action_prompt = f"Execute: SOP={json.dumps(sop_data)}, Vision={json.dumps(vision_data)}"
        action_results = invoke_agentcore_agent(
            "quality_inspection_action",
            action_prompt,
            "action"
        )
        action_data = parse_agent_response(action_results, "action")
        
        # Step 5: Communication Agent - ERP integration
        comm_prompt = f"Communicate: Action={json.dumps(action_data)}, SOP={json.dumps(sop_data)}"
        comm_results = invoke_agentcore_agent(
            "quality_inspection_communication",
            comm_prompt,
            "communication"
        )
        comm_data = parse_agent_response(comm_results, "communication")
        
        # Step 6: Store complete workflow results
        # Ensure vision_data is a dict before unpacking
        if isinstance(vision_data, dict) and 'defect_detected' in vision_data:
            complete_data = {
                **vision_data,
                'image_path': image_path,
                'analysis_results': analysis_data,
                'sop_decision': sop_data,
                'action_taken': action_data,
                'communications': comm_data
            }
        else:
            # Handle case where vision_data is not a proper dict
            complete_data = {
                'defect_detected': 'U',
                'analysis_summary': f'Vision data parsing error: {str(vision_data)[:200]}',
                'confidence': 0,
                'defects': [],
                'image_path': image_path,
                'analysis_results': analysis_data,
                'sop_decision': sop_data,
                'action_taken': action_data,
                'communications': comm_data
            }
        
        storage_result = store_inspection_results(complete_data)
        
        # Step 7: File operations based on SOP decision
        disposition = sop_data.get('disposition', 'review') if isinstance(sop_data, dict) else 'review'
        if disposition == 'scrap':
            defect_status = 'Y'
        elif disposition == 'accept':
            defect_status = 'N'
        else:
            defect_status = vision_data.get('defect_detected', 'U') if isinstance(vision_data, dict) and 'defect_detected' in vision_data else 'U'
            
        file_result = move_processed_file(
            image_path, 
            defect_status, 
            vision_data.get('defects', []) if isinstance(vision_data, dict) and 'defects' in vision_data else []
        )
        
        # Generate comprehensive workflow summary
        defect_count = len(vision_data.get('defects', [])) if isinstance(vision_data, dict) else 0
        defect_detected = vision_data.get('defect_detected', 'U') if isinstance(vision_data, dict) else 'U'
        confidence = vision_data.get('confidence', 0) if isinstance(vision_data, dict) else 0
        
        workflow_summary = f"""
🔍 **COMPLETE QUALITY INSPECTION WORKFLOW RESULTS**

**Image**: {image_path}

**1. VISION ANALYSIS**
- Defects Found: {defect_count}
- Status: {defect_detected}
- Confidence: {confidence}%

**2. QUALITY ANALYTICS**
- Quality Score: {analysis_data.get('quality_score', 'N/A')}
- Trend: {analysis_data.get('defect_rate_trend', 'N/A')}
- Maintenance: {analysis_data.get('maintenance_prediction', 'N/A')}

**3. SOP COMPLIANCE**
- Disposition: {sop_data.get('disposition', 'N/A').upper()}
- Rule Applied: {sop_data.get('sop_rule', 'N/A')}
- Action Required: {sop_data.get('action_required', 'N/A')}

**4. PHYSICAL ACTIONS**
- Action: {action_data.get('physical_action', 'N/A')}
- File Location: {action_data.get('file_location', 'N/A')}
- Production Impact: {action_data.get('production_impact', 'N/A')}

**5. COMMUNICATIONS**
- Notifications: {len(comm_data.get('notifications_sent', []))}
- ERP Updates: {len(comm_data.get('erp_updates', []))}
- Escalations: {len(comm_data.get('escalations', []))}

**FINAL STATUS**: {'🔴 REJECTED' if disposition == 'scrap' else '🟡 REWORK' if disposition == 'rework' else '🟢 ACCEPTED'}

{storage_result}
{file_result}

✅ **5-Agent Workflow Status: COMPLETED**
"""
        
        return workflow_summary
        
    except Exception as e:
        return f"Multi-agent workflow failed: {str(e)}"


def create_orchestrator_agent():
    """
    Create and configure the quality inspection orchestrator agent.
    
    Returns:
        Configured Strands Agent for orchestrating quality inspections
    """
    # Configure model for orchestration
    model_id = get_model_id()
    nova_model = BedrockModel(
        model_id=model_id
    )
    
    # Create orchestrator with routing tools
    agent = Agent(
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        model=nova_model,
        tools=[
            execute_full_workflow,
            visual_inspection_service,
            move_processed_file
        ]
    )
    
    return agent


def main():
    """
    Main function to run the quality inspection orchestrator.
    """
    if app:
        # AgentCore mode
        app.run()
    else:
        # Local development mode
        print("Quality Inspection Orchestrator")
        print("=" * 40)
        
        # Create the orchestrator
        orchestrator = create_orchestrator_agent()
        
        # Interactive mode
        while True:
            try:
                user_input = input("\nEnter inspection request (or 'quit' to exit): ")
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                    
                # Process the request through orchestrator
                response = orchestrator(user_input)
                print(f"\nOrchestrator Response:\n{response}")
                
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    main()