#!/usr/bin/env python3
"""
Test script for Action Agent
"""

import boto3
import json
import uuid
import time

def test_action_agent():
    """Test the action agent with sample SOP and vision data"""
    
    # Get action agent ARN from Parameter Store
    ssm = boto3.client('ssm')
    try:
        param = ssm.get_parameter(Name='/quality-inspection/agentcore-runtime/action')
        action_arn = param['Parameter']['Value']
        print(f"✅ Found action ARN: {action_arn}")
    except Exception as e:
        print(f"❌ Failed to get action ARN: {e}")
        return False
    
    # Create AgentCore client
    agentcore_client = boto3.client('bedrock-agentcore')
    
    # Sample SOP and vision data for action execution
    sample_sop_data = {
        "disposition": "rework",
        "sop_rule": "SOP-DEF-001",
        "action_required": "surface_refinishing"
    }
    
    sample_vision_data = {
        "defect_detected": "Y",
        "defects": [
            {
                "type": "Scratch",
                "description": "Small scratch in upper area",
                "grid_x1": 3,
                "grid_y1": 2,
                "grid_x2": 4,
                "grid_y2": 3
            }
        ],
        "confidence": 85
    }
    
    # Create test payload
    payload = json.dumps({
        "prompt": f"Execute physical actions based on: SOP={json.dumps(sample_sop_data)}, Vision={json.dumps(sample_vision_data)}"
    }).encode()
    
    # Generate unique session ID
    session_id = f"action-test-{uuid.uuid4().hex}-{int(time.time())}"
    
    try:
        print(f"🔄 Testing action agent with SOP and vision data")
        print(f"📋 Session ID: {session_id}")
        
        # Invoke the action agent
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=action_arn,
            runtimeSessionId=session_id,
            payload=payload
        )
        
        # Parse response
        if 'response' in response:
            response_content = ""
            for chunk in response['response']:
                response_content += chunk.decode('utf-8')
            
            if response_content:
                try:
                    result = json.loads(response_content)
                    print("✅ Action Agent Response:")
                    print(json.dumps(result, indent=2))
                    
                    # Extract and display key actions
                    if 'body' in result and 'result' in result['body']:
                        body_result = result['body']['result']
                        if isinstance(body_result, str) and 'AgentResult' in body_result:
                            print(f"\n🔧 Action execution completed - AgentCore response received")
                        else:
                            print(f"\n🔧 Action Result: {str(body_result)[:200]}...")
                        
                    return True
                except json.JSONDecodeError:
                    print("✅ Action Agent Response (text):")
                    print(response_content)
                    return True
            else:
                print("❌ Empty response from action agent")
                return False
        else:
            print("❌ No response from action agent")
            return False
            
    except Exception as e:
        print(f"❌ Error testing action agent: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Action Agent")
    print("=" * 28)
    
    success = test_action_agent()
    
    if success:
        print("\n✅ Action agent test completed successfully!")
    else:
        print("\n❌ Action agent test failed!")