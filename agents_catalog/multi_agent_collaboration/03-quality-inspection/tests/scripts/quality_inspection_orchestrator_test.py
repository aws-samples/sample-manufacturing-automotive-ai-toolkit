#!/usr/bin/env python3
"""
Test script for Quality Inspection Orchestrator Agent
"""

import boto3
import json
import uuid
import time
import os

def test_orchestrator_agent():
    """Test the orchestrator agent with a sample inspection request"""
    
    # Get orchestrator agent ARN from Parameter Store
    ssm = boto3.client('ssm')
    try:
        param = ssm.get_parameter(Name='/quality-inspection/agentcore-runtime/orchestrator')
        orchestrator_arn = param['Parameter']['Value']
        print(f"✅ Found orchestrator ARN: {orchestrator_arn}")
    except Exception as e:
        print(f"❌ Failed to get orchestrator ARN: {e}")
        return False
    
    # Create AgentCore client
    agentcore_client = boto3.client('bedrock-agentcore')
    
    # Upload local test image to S3
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_image_path = os.path.join(script_dir, "../test_images/anomalies/image1.jpg")
    
    if not os.path.exists(local_image_path):
        print(f"❌ Test image not found: {local_image_path}")
        return False
    
    # Upload to S3
    s3 = boto3.client('s3')
    
    # Get bucket name from SSM parameter
    ssm = boto3.client('ssm')
    try:
        bucket_name = ssm.get_parameter(Name='/quality-inspection/s3-bucket-name')['Parameter']['Value']
    except Exception as e:
        print(f"❌ Failed to get bucket name from SSM: {e}")
        return False
    s3_key = f"uploads/orchestrator_test_{int(time.time())}.jpg"
    
    try:
        with open(local_image_path, 'rb') as f:
            s3.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=f.read(),
                ContentType='image/jpeg'
            )
        test_image_path = f"s3://{bucket_name}/{s3_key}"
        print(f"✅ Uploaded test image: {test_image_path}")
    except Exception as e:
        print(f"❌ Failed to upload test image: {e}")
        return False
    
    # Create test payload
    payload = json.dumps({
        "prompt": f"Execute full quality inspection workflow for image: {test_image_path}"
    }).encode()
    
    # Generate unique session ID
    session_id = f"orchestrator-test-{uuid.uuid4().hex}-{int(time.time())}"
    
    try:
        print(f"🔄 Testing orchestrator with image: {test_image_path}")
        print(f"📋 Session ID: {session_id}")
        
        # Invoke the orchestrator agent
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=orchestrator_arn,
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
                    print("✅ Orchestrator Response:")
                    print(json.dumps(result, indent=2))
                    return True
                except json.JSONDecodeError:
                    print("✅ Orchestrator Response (text):")
                    print(response_content)
                    return True
            else:
                print("❌ Empty response from orchestrator")
                return False
        else:
            print("❌ No response from orchestrator")
            return False
            
    except Exception as e:
        print(f"❌ Error testing orchestrator: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Quality Inspection Orchestrator Agent")
    print("=" * 50)
    
    success = test_orchestrator_agent()
    
    if success:
        print("\n✅ Orchestrator test completed successfully!")
    else:
        print("\n❌ Orchestrator test failed!")