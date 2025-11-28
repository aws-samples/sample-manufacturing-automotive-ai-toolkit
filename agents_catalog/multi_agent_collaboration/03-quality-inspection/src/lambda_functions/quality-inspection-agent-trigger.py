import json
import boto3
import urllib.parse
import uuid
import os
from datetime import datetime



def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    
    # No need for DynamoDB or S3 clients - AgentCore handles everything
    
    try:
        for record in event['Records']:
            bucket = record['s3']['bucket']['name']
            key = urllib.parse.unquote_plus(record['s3']['object']['key'])
            
            # Only process images in inputimages folder
            if key.startswith('inputimages/'):
                print(f"Processing image: {key}")
                
                # Call AgentCore orchestrator - it handles everything
                result = call_agentcore_orchestrator(bucket, key)
                
                if result.get('status') == 'triggered':
                    print(f"✅ AgentCore workflow triggered for {key}")
                else:
                    print(f"❌ Failed to trigger AgentCore for {key}: {result.get('error')}")
        
        return {'statusCode': 200, 'body': 'Processing complete'}
        
    except Exception as e:
        print(f"Error processing event: {str(e)}")
        return {'statusCode': 500, 'body': f'Error: {str(e)}'}

def call_agentcore_orchestrator(bucket, key):
    try:
        # Call AgentCore Runtime with proper endpoint
        agentcore_client = boto3.client('bedrock-agentcore')
        agentcore_control_client = boto3.client('bedrock-agentcore-control')
        
        # Construct S3 path for the image
        s3_path = f"s3://{bucket}/{key}"
        
        # Prepare payload
        payload = json.dumps({
            "prompt": f"Analyze manufacturing part image at {s3_path} for quality defects"
        }).encode()
        
        # Get orchestrator ARN from Parameter Store
        ssm = boto3.client('ssm')
        try:
            orchestrator_param = ssm.get_parameter(Name='/quality-inspection/agentcore-runtime/orchestrator')
            orchestrator_arn = orchestrator_param['Parameter']['Value']
        except Exception as e:
            return {
                'status': 'error',
                'error': f'Orchestrator ARN not found in Parameter Store: {str(e)}',
                'message': 'Could not retrieve orchestrator runtime ARN from SSM'
            }
        
        # Call AgentCore orchestrator
        print(f"Calling orchestrator: {orchestrator_arn}")
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=orchestrator_arn,
            runtimeSessionId=f"session-{uuid.uuid4().hex}",
            payload=payload
        )
        
        # Parse AgentCore response properly (like our successful tests)
        response_text = ""
        if 'response' in response:
            # Read the streaming response chunks
            for chunk in response['response']:
                response_text += chunk.decode('utf-8')
        
        print(f"AgentCore response: {response_text}")
        
        # Parse the JSON response to check for success
        try:
            response_data = json.loads(response_text)
            if 'response' in response_data:
                print(f"✅ Orchestrator completed: {response_data['response'][:200]}...")
            else:
                print(f"⚠️ Unexpected response format: {response_data}")
        except json.JSONDecodeError:
            print(f"⚠️ Could not parse response as JSON: {response_text[:200]}...")
        
        return {
            'status': 'triggered',
            'response': response_text,
            'message': 'AgentCore workflow triggered successfully'
        }
        
    except Exception as e:
        print(f"AgentCore call error: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'message': f'Failed to trigger AgentCore for {key}'
        }



