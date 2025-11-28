#!/usr/bin/env python3
"""
Test script for Communication Agent
"""

import boto3
import json
import uuid
import time

def test_communication_agent():
    """Test the communication agent with sample action and SOP data"""
    
    # Get communication agent ARN from Parameter Store
    ssm = boto3.client('ssm')
    try:
        param = ssm.get_parameter(Name='/quality-inspection/agentcore-runtime/communication')
        comm_arn = param['Parameter']['Value']
        print(f"✅ Found communication ARN: {comm_arn}")
    except Exception as e:
        print(f"❌ Failed to get communication ARN: {e}")
        return False
    
    # Create AgentCore client
    agentcore_client = boto3.client('bedrock-agentcore')
    
    # Sample action and SOP data for communication
    sample_action_data = {
        "physical_action": "move_to_rework_station",
        "file_location": "rework/",
        "production_impact": "minimal"
    }
    
    sample_sop_data = {
        "disposition": "rework",
        "sop_rule": "SOP-DEF-001",
        "action_required": "surface_refinishing"
    }
    
    # Create test payload
    payload = json.dumps({
        "prompt": f"Handle communications and notifications for: Action={json.dumps(sample_action_data)}, SOP={json.dumps(sample_sop_data)}"
    }).encode()
    
    # Generate unique session ID
    session_id = f"comm-test-{uuid.uuid4().hex}-{int(time.time())}"
    
    try:
        print(f"🔄 Testing communication agent with action and SOP data")
        print(f"📋 Session ID: {session_id}")
        
        # Invoke the communication agent
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=comm_arn,
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
                    print("✅ Communication Agent Response:")
                    print(json.dumps(result, indent=2))
                    
                    # Extract and display key communications
                    if 'body' in result and 'result' in result['body']:
                        body_result = result['body']['result']
                        if isinstance(body_result, str) and 'AgentResult' in body_result:
                            print(f"\n📢 Communication completed - AgentCore response received")
                        else:
                            print(f"\n📢 Communication Result: {str(body_result)[:200]}...")
                        
                    return True
                except json.JSONDecodeError:
                    print("✅ Communication Agent Response (text):")
                    print(response_content)
                    return True
            else:
                print("❌ Empty response from communication agent")
                return False
        else:
            print("❌ No response from communication agent")
            return False
            
    except Exception as e:
        print(f"❌ Error testing communication agent: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Communication Agent")
    print("=" * 35)
    
    success = test_communication_agent()
    
    if success:
        print("\n✅ Communication agent test completed successfully!")
    else:
        print("\n❌ Communication agent test failed!")