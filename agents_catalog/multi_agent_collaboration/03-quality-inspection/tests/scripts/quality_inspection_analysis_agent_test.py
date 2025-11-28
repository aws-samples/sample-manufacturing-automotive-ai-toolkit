#!/usr/bin/env python3
"""
Test script for Analysis Agent
"""

import boto3
import json
import uuid
import time

def test_analysis_agent():
    """Test the analysis agent with sample defect data"""
    
    # Get analysis agent ARN from Parameter Store
    ssm = boto3.client('ssm')
    try:
        param = ssm.get_parameter(Name='/quality-inspection/agentcore-runtime/analysis')
        analysis_arn = param['Parameter']['Value']
        print(f"✅ Found analysis ARN: {analysis_arn}")
    except Exception as e:
        print(f"❌ Failed to get analysis ARN: {e}")
        return False
    
    # Create AgentCore client
    agentcore_client = boto3.client('bedrock-agentcore')
    
    # Sample vision data for analysis
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
        "prompt": f"Analyze quality trends and patterns from this inspection data: {json.dumps(sample_vision_data)}"
    }).encode()
    
    # Generate unique session ID
    session_id = f"analysis-test-{uuid.uuid4().hex}-{int(time.time())}"
    
    try:
        print(f"🔄 Testing analysis agent with sample defect data")
        print(f"📋 Session ID: {session_id}")
        
        # Invoke the analysis agent
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=analysis_arn,
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
                    print("✅ Analysis Agent Response:")
                    print(json.dumps(result, indent=2))
                    
                    # Extract and display key analysis
                    if 'body' in result and 'result' in result['body']:
                        body_result = result['body']['result']
                        if isinstance(body_result, str) and 'AgentResult' in body_result:
                            print(f"\n📊 Analysis completed - AgentCore response received")
                        else:
                            print(f"\n📊 Analysis Result: {str(body_result)[:200]}...")
                        
                    return True
                except json.JSONDecodeError:
                    print("✅ Analysis Agent Response (text):")
                    print(response_content)
                    return True
            else:
                print("❌ Empty response from analysis agent")
                return False
        else:
            print("❌ No response from analysis agent")
            return False
            
    except Exception as e:
        print(f"❌ Error testing analysis agent: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Analysis Agent")
    print("=" * 30)
    
    success = test_analysis_agent()
    
    if success:
        print("\n✅ Analysis agent test completed successfully!")
    else:
        print("\n❌ Analysis agent test failed!")