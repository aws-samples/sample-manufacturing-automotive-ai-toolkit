#!/usr/bin/env python3
"""
Test script for SOP Agent
"""

import boto3
import json
import uuid
import time

def test_sop_agent():
    """Test the SOP agent with sample defect data"""
    
    # Get SOP agent ARN from Parameter Store
    ssm = boto3.client('ssm')
    try:
        param = ssm.get_parameter(Name='/quality-inspection/agentcore-runtime/sop')
        sop_arn = param['Parameter']['Value']
        print(f"✅ Found SOP ARN: {sop_arn}")
    except Exception as e:
        print(f"❌ Failed to get SOP ARN: {e}")
        return False
    
    # Create AgentCore client
    agentcore_client = boto3.client('bedrock-agentcore')
    
    # Sample vision data for SOP decision
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
        "confidence": 85,
        "analysis_summary": "Found 1 defect: scratch in upper area"
    }
    
    # Create test payload
    payload = json.dumps({
        "prompt": f"Make SOP compliance decision for this inspection result: {json.dumps(sample_vision_data)}"
    }).encode()
    
    # Generate unique session ID
    session_id = f"sop-test-{uuid.uuid4().hex}-{int(time.time())}"
    
    try:
        print(f"🔄 Testing SOP agent with defect data")
        print(f"📋 Session ID: {session_id}")
        
        # Invoke the SOP agent
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=sop_arn,
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
                    print("✅ SOP Agent Response:")
                    print(json.dumps(result, indent=2))
                    
                    # Extract and display key SOP decision
                    if 'body' in result and 'result' in result['body']:
                        body_result = result['body']['result']
                        if isinstance(body_result, str) and 'AgentResult' in body_result:
                            print(f"\n⚖️ SOP decision completed - AgentCore response received")
                        else:
                            print(f"\n⚖️ SOP Result: {str(body_result)[:200]}...")
                        
                    return True
                except json.JSONDecodeError:
                    print("✅ SOP Agent Response (text):")
                    print(response_content)
                    return True
            else:
                print("❌ Empty response from SOP agent")
                return False
        else:
            print("❌ No response from SOP agent")
            return False
            
    except Exception as e:
        print(f"❌ Error testing SOP agent: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing SOP Agent")
    print("=" * 25)
    
    success = test_sop_agent()
    
    if success:
        print("\n✅ SOP agent test completed successfully!")
    else:
        print("\n❌ SOP agent test failed!")