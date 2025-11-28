#!/usr/bin/env python3
"""
Test script for Vision Agent
"""

import boto3
import json
import uuid
import time
import os

def test_vision_agent():
    """Test the vision agent with sample images"""
    
    # Get vision agent ARN from Parameter Store
    ssm = boto3.client('ssm')
    try:
        param = ssm.get_parameter(Name='/quality-inspection/agentcore-runtime/vision')
        vision_arn = param['Parameter']['Value']
        print(f"✅ Found vision ARN: {vision_arn}")
    except Exception as e:
        print(f"❌ Failed to get vision ARN: {e}")
        return False
    
    # Get reference image S3 URI
    try:
        ref_param = ssm.get_parameter(Name='/quality-inspection/reference-image-s3-uri')
        reference_s3_url = ref_param['Parameter']['Value']
        print(f"✅ Found reference image: {reference_s3_url}")
    except Exception as e:
        print(f"❌ Failed to get reference image URI: {e}")
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
    s3_key = f"uploads/test_image_{int(time.time())}.jpg"
    
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
    
    # Create test payload with both reference and test images
    payload = json.dumps({
        "prompt": f"Analyze these images for defects: Reference={reference_s3_url}, Test={test_image_path}",
        "reference_s3_url": reference_s3_url,
        "test_s3_url": test_image_path
    }).encode()
    
    # Generate unique session ID
    session_id = f"vision-test-{uuid.uuid4().hex}-{int(time.time())}"
    
    try:
        print(f"🔄 Testing vision agent with:")
        print(f"   Reference: {reference_s3_url}")
        print(f"   Test: {test_image_path}")
        print(f"📋 Session ID: {session_id}")
        
        # Invoke the vision agent
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=vision_arn,
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
                    print("✅ Vision Agent Response:")
                    print(json.dumps(result, indent=2))
                    
                    # Extract and display key findings
                    if 'body' in result and 'result' in result['body']:
                        vision_result = json.loads(result['body']['result'])
                        print(f"\n🔍 Vision Analysis Summary:")
                        print(f"   Defects Detected: {vision_result.get('defect_detected', 'Unknown')}")
                        print(f"   Confidence: {vision_result.get('confidence', 0)}%")
                        print(f"   Defect Count: {len(vision_result.get('defects', []))}")
                        
                    return True
                except json.JSONDecodeError:
                    print("✅ Vision Agent Response (text):")
                    print(response_content)
                    return True
            else:
                print("❌ Empty response from vision agent")
                return False
        else:
            print("❌ No response from vision agent")
            return False
            
    except Exception as e:
        print(f"❌ Error testing vision agent: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Vision Agent")
    print("=" * 30)
    
    success = test_vision_agent()
    
    if success:
        print("\n✅ Vision agent test completed successfully!")
    else:
        print("\n❌ Vision agent test failed!")