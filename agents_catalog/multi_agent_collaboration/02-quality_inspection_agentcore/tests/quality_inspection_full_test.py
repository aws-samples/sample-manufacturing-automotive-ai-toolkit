#!/usr/bin/env python3

import boto3
import json
import time
import sys
import os
from datetime import datetime

def get_boto3_client(service_name, region_name='us-east-1'):
    """Get boto3 client with profile support"""
    try:
        session = boto3.Session(profile_name='grantaws')
        return session.client(service_name, region_name=region_name)
    except:
        return boto3.client(service_name, region_name=region_name)

def get_boto3_resource(service_name, region_name='us-east-1'):
    """Get boto3 resource with profile support"""
    try:
        session = boto3.Session(profile_name='grantaws')
        return session.resource(service_name, region_name=region_name)
    except:
        return boto3.resource(service_name, region_name=region_name)

def discover_bucket():
    """Discover the quality inspection S3 bucket"""
    try:
        # Try CloudFormation stacks first
        cf = get_boto3_client('cloudformation')
        stacks = ['QualityInspectionStack', 'AgenticQualityInspectionStack', 'MA3TMainStack']
        
        for stack_name in stacks:
            try:
                response = cf.describe_stacks(StackName=stack_name)
                outputs = response['Stacks'][0].get('Outputs', [])
                for output in outputs:
                    key = output['OutputKey'].lower()
                    if any(word in key for word in ['bucket', 'machinepartimages', 'resourcebucket']):
                        return output['OutputValue']
            except:
                continue
        
        # Fallback to account-based naming
        sts = get_boto3_client('sts')
        account_id = sts.get_caller_identity()['Account']
        return f"machinepartimages-{account_id}"
        
    except Exception as e:
        print(f"Error discovering bucket: {e}")
        return "machinepartimages"

def upload_test_image(bucket_name, test_image_path):
    """Upload test image to S3 inputimages folder"""
    try:
        s3 = get_boto3_client('s3')
        filename = os.path.basename(test_image_path)
        s3_key = f"inputimages/{filename}"
        
        with open(test_image_path, 'rb') as f:
            s3.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=f.read(),
                ContentType='image/jpeg'
            )
        
        print(f"✅ Uploaded {filename} to s3://{bucket_name}/{s3_key}")
        return s3_key
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return None

def monitor_workflow(filename, max_wait=120):
    """Monitor DynamoDB for workflow completion"""
    try:
        dynamodb = get_boto3_resource('dynamodb')
        table = dynamodb.Table('vision-inspection-data')
        
        print(f"🔍 Monitoring workflow for {filename}...")
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                # Search by image_key containing filename
                response = table.scan(
                    FilterExpression=boto3.dynamodb.conditions.Attr('image_key').contains(filename)
                )
                
                if response['Items']:
                    # Get most recent result
                    items = sorted(response['Items'], key=lambda x: x.get('timestamp', ''), reverse=True)
                    result = items[0]
                    print(f"✅ Workflow completed for {filename}")
                    return result
                    
            except Exception as e:
                print(f"⚠️ Error checking DynamoDB: {e}")
            
            print(f"⏳ Waiting... ({int(time.time() - start_time)}s)")
            time.sleep(10)
        
        print(f"⏰ Timeout after {max_wait}s - workflow may still be processing")
        return None
        
    except Exception as e:
        print(f"❌ Monitoring failed: {e}")
        return None

def display_results(result):
    """Display workflow results"""
    if not result:
        print("❌ No results found")
        return
    
    print("\n" + "="*50)
    print("📊 QUALITY INSPECTION RESULTS")
    print("="*50)
    
    # Basic info
    print(f"🔍 Image: {result.get('image_key', 'Unknown')}")
    print(f"⏰ Timestamp: {result.get('timestamp', 'Unknown')}")
    print(f"🆔 Inspection ID: {result.get('inspection_id', 'Unknown')}")
    
    # Defect detection
    defect_detected = result.get('defect_detected', 'Unknown')
    if defect_detected == 'Y':
        print("🚨 DEFECTS DETECTED")
        defects = result.get('defects', [])
        for i, defect in enumerate(defects, 1):
            print(f"  Defect {i}: {defect.get('type', 'Unknown')}")
            print(f"    Description: {defect.get('description', 'No description')}")
            if all(k in defect for k in ['grid_x1', 'grid_y1', 'grid_x2', 'grid_y2']):
                print(f"    Location: Grid ({defect['grid_x1']},{defect['grid_y1']}) to ({defect['grid_x2']},{defect['grid_y2']})")
    elif defect_detected == 'N':
        print("✅ NO DEFECTS DETECTED")
    else:
        print(f"❓ Defect status: {defect_detected}")
    
    # Recommendation
    recommendation = result.get('recommendation', result.get('disposition', 'Unknown'))
    if recommendation == 'PASS':
        print("✅ SOP RECOMMENDATION: PASS")
    elif recommendation == 'FAIL':
        print("❌ SOP RECOMMENDATION: FAIL")
    elif recommendation == 'REVIEW':
        print("⚠️ SOP RECOMMENDATION: REVIEW (Manual inspection required)")
    else:
        print(f"📋 SOP RECOMMENDATION: {recommendation}")
    
    # Confidence
    confidence = result.get('confidence')
    if confidence:
        print(f"🎯 Confidence: {confidence}%")
    
    print("="*50)

def main():
    print("🏭 Quality Inspection Full Workflow Test")
    print("="*50)
    
    # Check if test image exists
    script_dir = os.path.dirname(os.path.abspath(__file__))
    test_image_path = os.path.join(script_dir, "test_images/anomalies/image1.jpg")
    if not os.path.exists(test_image_path):
        print(f"❌ Test image not found: {test_image_path}")
        sys.exit(1)
    
    # Discover bucket
    print("🔍 Discovering S3 bucket...")
    bucket_name = discover_bucket()
    print(f"📦 Using bucket: {bucket_name}")
    
    # Upload test image
    print("📤 Uploading test image...")
    s3_key = upload_test_image(bucket_name, test_image_path)
    if not s3_key:
        sys.exit(1)
    
    filename = os.path.basename(test_image_path)
    
    # Monitor workflow
    result = monitor_workflow(filename)
    
    # Display results
    display_results(result)
    
    if result:
        print("\n✅ Test completed successfully!")
        return 0
    else:
        print("\n❌ Test failed or timed out")
        return 1

if __name__ == "__main__":
    sys.exit(main())