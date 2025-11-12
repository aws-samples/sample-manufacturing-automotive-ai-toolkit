"""
Vision Agent - Computer vision-based defect detection using Amazon Nova Pro
Ready for Amazon Bedrock AgentCore deployment
"""
import os
os.environ["BYPASS_TOOL_CONSENT"]="true"

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
import json
import boto3
import base64
from io import BytesIO
from model_config import get_model_id

# Initialize AgentCore App
app = BedrockAgentCoreApp()

@app.entrypoint
def handler(event):
    """AgentCore entrypoint for Vision Agent"""
    try:
        # Extract parameters from event
        prompt = event.get("prompt", "")
        reference_s3_url = event.get("reference_s3_url", "")
        test_s3_url = event.get("test_s3_url", "")
        

        
        # If we have both S3 URLs, create multimodal message
        if reference_s3_url and test_s3_url:
            # Read images from S3 as bytes
            s3 = boto3.client('s3')
            
            # Parse S3 URIs more robustly
            def parse_s3_url(s3_url):
                if s3_url.startswith('s3://'):
                    parts = s3_url[5:].split('/', 1)
                    bucket = parts[0]
                    key = parts[1] if len(parts) > 1 else ''
                    return bucket, key
                else:
                    raise ValueError(f"Invalid S3 URL format: {s3_url}")
            
            ref_bucket, ref_key = parse_s3_url(reference_s3_url)
            test_bucket, test_key = parse_s3_url(test_s3_url)
            
            # Get images as bytes
            ref_obj = s3.get_object(Bucket=ref_bucket, Key=ref_key)
            test_obj = s3.get_object(Bucket=test_bucket, Key=test_key)
            
            ref_bytes = ref_obj['Body'].read()
            test_bytes = test_obj['Body'].read()
            
            # Encode as base64
            ref_encoded = base64.b64encode(ref_bytes).decode()
            test_encoded = base64.b64encode(test_bytes).decode()
            
            # Create multimodal content blocks
            content_blocks = [
                {
                    "text": "CRITICAL DEFECT INSPECTION: Compare these manufacturing parts carefully.\n\nFirst image: CLEAN REFERENCE (perfect condition)\nSecond image: TEST PART (inspect for ANY differences)\n\nIMPORTANT COORDINATE SYSTEM:\n- Divide the TEST image into a precise 10x10 grid (100 cells total)\n- Grid coordinates: (1,1) = top-left corner, (10,10) = bottom-right corner\n- Columns 1-10 go left to right, Rows 1-10 go top to bottom\n- Column 5-6 = center horizontally, Row 1-2 = top area\n- Be EXTREMELY PRECISE - look carefully at WHERE the defect actually appears\n\nCRITICAL: For small defects:\n- Use minimal bounding boxes (1-2 grid cells only)\n- Identify the EXACT grid position where you see the defect\n- Do NOT guess or use large areas - be precise about location\n- If defect is in top-middle, use coordinates like (5,1) to (6,2)\n- If defect is small, coordinates should reflect actual size\n\nLook for ANY visible differences including:\n- Scratches (any size, even tiny ones)\n- Cracks (hairline or obvious)\n- Dents, chips, or surface damage\n- Color variations or discoloration\n\nRespond ONLY with valid JSON: {\"defect_detected\": \"Y\", \"defects\": [{\"type\": \"Scratch\", \"description\": \"location\", \"grid_x1\": 1, \"grid_y1\": 1, \"grid_x2\": 2, \"grid_y2\": 2}], \"confidence\": 85, \"analysis_summary\": \"findings\"}"
                },
                {
                    "image": {
                        "format": "jpeg",
                        "source": {
                            "bytes": ref_bytes
                        }
                    }
                },
                {
                    "image": {
                        "format": "jpeg",
                        "source": {
                            "bytes": test_bytes
                        }
                    }
                }
            ]
            
            result = vision_agent(content_blocks)
        else:
            result = vision_agent(prompt)
        
        result_str = str(result)
        
        return {
            "statusCode": 200,
            "body": {
                "agent_type": "vision",
                "result": result_str,
                "success": True
            }
        }
        
    except Exception as e:
        error_msg = str(e)
        return {
            "statusCode": 500,
            "body": {
                "agent_type": "vision",
                "result": f'{{"defect_detected": "U", "analysis_summary": "Error: {error_msg[:200]}", "confidence": 0, "defects": []}}',
                "success": False
            }
        }

# Create Strands vision agent with multimodal support
model_id = get_model_id()
bedrock_model = BedrockModel(
    model_id=model_id,
    temperature=0.1
)

vision_agent = Agent(
    model=bedrock_model,
    system_prompt="""You are a vision inspection agent for manufacturing defect detection using Amazon Nova Pro.

You MUST respond with ONLY valid JSON, no other text.

Analyze the provided images directly for defects.
Compare reference (perfect) vs test (inspect) images.
Use 10x10 grid coordinates for defect locations.
Look for scratches, cracks, dents, chips, discoloration.

Return ONLY this JSON format:
{"defect_detected": "Y", "defects": [{"type": "Scratch", "description": "Small scratch in upper area", "grid_x1": 1, "grid_y1": 1, "grid_x2": 2, "grid_y2": 2}], "confidence": 85, "analysis_summary": "Found 1 defect"}

If no defects:
{"defect_detected": "N", "defects": [], "confidence": 95, "analysis_summary": "No defects detected"}

Respond with JSON only, no explanations."""
)

if __name__ == "__main__":
    app.run()