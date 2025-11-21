import streamlit as st
import boto3
import json
from datetime import datetime
from PIL import Image, ImageDraw
import io
import uuid
import base64
import sys
import os
import tempfile
import atexit
import time
import argparse

# Add src directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Global AWS profile setting
AWS_PROFILE = None

# MUST be first Streamlit command
st.set_page_config(
    page_title="Modular Multi-Agent Quality Inspection",
    page_icon="🏭",
    layout="wide"
)

def get_boto3_session():
    """Get boto3 session with optional profile"""
    if AWS_PROFILE:
        return boto3.Session(profile_name=AWS_PROFILE)
    return boto3.Session()

def get_boto3_client(service_name, region_name=None):
    """Get boto3 client with optional profile"""
    session = get_boto3_session()
    if region_name:
        return session.client(service_name, region_name=region_name)
    return session.client(service_name)

def get_boto3_resource(service_name, region_name=None):
    """Get boto3 resource with optional profile"""
    session = get_boto3_session()
    if region_name:
        return session.resource(service_name, region_name=region_name)
    return session.resource(service_name)

# AgentCore agents - no local imports needed

def main():
    st.title("🏭 Modular Multi-Agent Quality Inspection")
    st.markdown("**Organized Agent Architecture with Separate Files**")
    
    # Initialize session state
    if 'initialized' not in st.session_state:
        st.session_state.agent_logs = []
        st.session_state.processing_history = []
        st.session_state.agent_communications = []
        st.session_state.last_processed_image = None
        st.session_state.last_processed_filename = None
        st.session_state.temp_image_path = None
        st.session_state.initialized = True
        atexit.register(cleanup_temp_images)  # Cleanup on exit
        with st.spinner("Loading recent results..."):
            # Auto-load recent results on startup
            try:
                region = 'us-east-1'
                load_recent_results(region)
                log_agent_activity("system", "AgentCore agents ready - no local initialization needed")
            except Exception as e:
                log_agent_activity("system", f"Failed to auto-load results: {str(e)}")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📸 Image Processing")
        
        # Region selection first
        region = st.selectbox("AWS Region", ["us-east-1", "us-west-2"], index=0)
        
        # S3 Configuration - Auto-discover bucket name
        bucket_name = discover_quality_inspection_bucket(region)
        # Validate bucket exists
        try:
            s3 = get_boto3_client('s3', region_name=region)
            s3.head_bucket(Bucket=bucket_name)
            st.success(f"📦 S3 Bucket: {bucket_name} ✅")
        except Exception as e:
            st.error(f"📦 S3 Bucket: {bucket_name} ❌ (Not found: {str(e)})")
            st.warning("Please check your CDK deployment or AWS credentials")
        
        # File upload section
        uploaded_file = st.file_uploader("Upload Image", type=['jpg', 'jpeg', 'png'])
        if uploaded_file and st.button("📤 Upload to S3 (Auto-triggers AgentCore)"):
            upload_result = upload_file_to_s3(uploaded_file, bucket_name, region)
            if upload_result['success']:
                st.success(f"✅ Uploaded: {upload_result['key']}")
                st.info("🤖 AgentCore workflow automatically triggered!")
                st.info("⏳ Processing will complete automatically - check results below")
                st.rerun()
            else:
                st.error(f"❌ Upload failed: {upload_result['error']}")
        
        # Show recent uploads for reference
        try:
            available_images = get_s3_objects(bucket_name, "inputimages/", region)
            if available_images:
                st.info(f"📁 Recent uploads: {len(available_images)} files in inputimages/")
                with st.expander("View recent uploads"):
                    for img in available_images[-5:]:  # Show last 5
                        st.text(f"• {img.split('/')[-1]}")
            else:
                st.info("📁 No files in inputimages/ folder yet")
        except Exception as e:
            st.warning(f"Could not access S3 bucket: {str(e)}")
        
        # AgentCore agents run remotely
        
        # Display images side by side
        ref_bucket = bucket_name
        ref_key = "cleanimages/Cleanimage.jpg"
        
        img_col1, img_col2 = st.columns(2)
        
        with img_col1:
            try:
                ref_image_bytes = download_s3_image(ref_bucket, ref_key, region)
                ref_image = Image.open(io.BytesIO(ref_image_bytes))
                st.image(ref_image, caption="Reference (Clean)", width='stretch')
            except Exception as e:
                st.warning(f"Could not load reference image: {str(e)}")
                st.info("Reference image should be at: s3://{bucket_name}/cleanimages/Cleanimage.jpg")
        
        with img_col2:
            if uploaded_file:
                # Show the uploaded image preview
                try:
                    uploaded_image = Image.open(uploaded_file)
                    st.image(uploaded_image, caption=f"Uploaded: {uploaded_file.name}", width='stretch')
                except:
                    st.info("Could not display uploaded image")
            elif available_images:
                # Show most recent uploaded image if no current upload
                try:
                    latest_image = available_images[-1]  # Most recent
                    test_image_bytes = download_s3_image(bucket_name, latest_image, region)
                    test_image = Image.open(io.BytesIO(test_image_bytes))
                    filename = latest_image.split('/')[-1]
                    st.image(test_image, caption=f"Latest Upload: {filename}", width='stretch')
                except:
                    st.info("Upload an image to see preview")
            else:
                st.info("Upload an image to see preview")
        
        # Auto-refresh for latest results
        if st.button("🔄 Refresh Results"):
            with st.spinner("Checking for latest processing results..."):
                load_recent_results(region)
                recent_count = len(st.session_state.processing_history)
                st.success(f"✅ Found {recent_count} recent processing results!")
                st.rerun()
    
    with col2:
        st.header("🤖 AgentCore Architecture")
        st.info("""
        **Amazon Bedrock AgentCore:**
        - Agents deployed in private VPC
        - Auto-scaling and managed runtime
        - Built-in memory and observability
        - **Automatic S3 trigger workflow**
        
        **AgentCore Agents:**
        - 🔍 quality_inspection_vision
        - 📋 quality_inspection_sop  
        - 🤖 quality_inspection_action
        - 📡 quality_inspection_communication
        - 🧠 quality_inspection_analysis
        - 🎭 quality_inspection_orchestrator
        
        **Workflow:**
        1. Upload image → S3 inputimages/
        2. Lambda auto-triggers orchestrator
        3. Multi-agent processing in VPC
        4. Results stored in DynamoDB
        """)
        

    
    # Agent status
    st.header("🎛️ AgentCore Status")
    display_agentcore_status()
    
    # Latest Results section
    if st.session_state.processing_history:
        latest = st.session_state.processing_history[0]
        if 'agentcore_results' in latest['result']:
            st.header("📈 Latest Results")
            
            # Show image name
            agentcore_data = latest['result']['agentcore_results']
            image_key = agentcore_data.get('image_key', '')
            filename = image_key.split('/')[-1] if image_key else latest['image']
            st.subheader(f"📸 Image: {filename}")
            
            # Display image with defect annotations
            if image_key:
                try:
                    bucket_name = discover_quality_inspection_bucket('us-east-1')
                    
                    # Check if image is in defects or processedimages folder
                    possible_keys = [f"defects/{filename}", f"processedimages/{filename}", image_key]
                    
                    for key in possible_keys:
                        try:
                            image_bytes = download_s3_image(bucket_name, key, 'us-east-1')
                            image = Image.open(io.BytesIO(image_bytes))
                            
                            # Use shared defect parsing function
                            defects = parse_and_display_defects(agentcore_data)
                            
                            # Annotate image with defects if any
                            if defects:
                                annotated_image = annotate_image_with_defects(image, defects)
                                st.image(annotated_image, caption=f"🔴 {len(defects)} defect(s) detected with red bounding boxes", width=400)
                                
                                # Debug info
                                st.info(f"**Debug:** Image: {key}, Size: {image.width}x{image.height}")
                                for i, defect in enumerate(defects):
                                    coords = f"({defect.get('grid_x1')},{defect.get('grid_y1')}) to ({defect.get('grid_x2')},{defect.get('grid_y2')})"
                                    st.info(f"**Defect {i+1}:** {defect.get('type')} at grid {coords}")
                            else:
                                st.image(image, caption=f"✅ No defects detected", width=400)
                            break
                        except:
                            continue
                except Exception as e:
                    st.info(f"Could not load image: {filename}")
            
            # Show recommendation
            recommendation = agentcore_data.get('recommendation', 'REVIEW')
            if recommendation == 'PASS':
                st.success(f"📋 SOP: {recommendation}")
            elif recommendation == 'FAIL':
                st.error(f"📋 SOP: {recommendation}")
            elif recommendation == 'REVIEW':
                st.warning(f"📋 SOP: {recommendation} (requires manual inspection)")
            else:
                st.warning(f"📋 SOP: {recommendation}")
            
            st.info("🤖 Action: File processed and moved")
            st.info("📡 Communication: Results logged")
            st.info("🧠 Analysis: Quality trends updated")
    
    # Agent execution log
    st.header("📋 Agent Execution Log")
    display_agent_logs()
    
    # Last processed image
    if hasattr(st.session_state, 'last_processed_image') and st.session_state.last_processed_image:
        st.header("📸 Last Processed Image")
        st.image(st.session_state.last_processed_image, 
                caption=f"Processed: {st.session_state.last_processed_filename}", 
                width='stretch')
    
    # Processing history
    st.header("📊 Processing History")
    display_processing_history()
    
    # Agent Communications
    st.header("💬 Agent Communications (JSON)")
    display_agent_communications()

# AgentCore agents run remotely - no local initialization needed

def load_recent_results(region):
    """Load recent processing results into session state"""
    try:
        # Get all recent results from DynamoDB directly
        recent_results = get_all_recent_results(region)
        
        # Update processing history with all recent results
        st.session_state.processing_history = []
        for result in recent_results[:5]:  # Show last 5 results
            filename = result.get('image_key', '').split('/')[-1] if result.get('image_key') else 'Unknown'
            timestamp = result.get('timestamp', '')
            if timestamp:
                # Convert ISO timestamp to display format
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    display_time = dt.strftime("%H:%M:%S")
                except:
                    display_time = timestamp[:8]  # Fallback
            else:
                display_time = datetime.now().strftime("%H:%M:%S")
            
            st.session_state.processing_history.append({
                'timestamp': display_time,
                'image': filename,
                'result': {
                    'status': 'success', 
                    'agentcore_results': result
                }
            })
        
        if recent_results:
            log_agent_activity("system", f"Loaded {len(recent_results)} recent processing results")
            
            # AgentCore logs will be loaded dynamically in display_agent_communications()
        
    except Exception as e:
        log_agent_activity("system", f"Failed to load recent results: {str(e)}")

# Removed trigger_agentcore_workflow - no longer needed since S3 auto-triggers

def parse_agent_response(response):
    """Parse agent response and extract JSON"""
    try:
        # Handle different response types
        if hasattr(response, 'content'):
            response_text = response.content
        elif isinstance(response, str):
            response_text = response
        else:
            response_text = str(response)
        
        # Try multiple JSON extraction methods
        try:
            return json.loads(response_text)
        except:
            pass
        
        # Find JSON block
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start != -1 and end > start:
            json_str = response_text[start:end]
            try:
                return json.loads(json_str)
            except:
                pass
        
        return {"error": "Could not parse agent response", "raw_response": response_text[:200]}
    except Exception as e:
        return {"error": f"Parse error: {str(e)}", "raw_response": str(response)[:200]}

def execute_s3_operations(bucket_name, s3_key, sop_data, vision_data, region):
    """Execute S3 file operations based on defect detection"""
    try:
        s3 = boto3.client('s3', region_name=region)
        filename = s3_key.split('/')[-1]
        
        if vision_data.get('defect_detected') == 'Y' and vision_data.get('defects'):
            # Move to defects folder and create JSON
            final_s3_key = f"defects/{filename}"
            s3.copy_object(
                Bucket=bucket_name,
                CopySource={'Bucket': bucket_name, 'Key': s3_key},
                Key=final_s3_key
            )
            
            # Create JSON file with defect details
            json_key = f"defects/{filename.rsplit('.', 1)[0]}.json"
            json_content = json.dumps(vision_data, indent=2)
            s3.put_object(
                Bucket=bucket_name,
                Key=json_key,
                Body=json_content,
                ContentType='application/json'
            )
            
            action_type = 'moved_to_defects'
        else:
            # Move to processedimages folder (no defects)
            final_s3_key = f"processedimages/{filename}"
            s3.copy_object(
                Bucket=bucket_name,
                CopySource={'Bucket': bucket_name, 'Key': s3_key},
                Key=final_s3_key
            )
            
            action_type = 'moved_to_processed'
        
        # Delete original
        s3.delete_object(Bucket=bucket_name, Key=s3_key)
        
        return {
            'action': action_type,
            'final_s3_key': final_s3_key,
            's3_operations': 'completed',
            'original_deleted': True
        }
        
    except Exception as e:
        return {'s3_error': str(e)}

def log_agent_activity(agent, activity):
    """Log agent activity"""
    st.session_state.agent_logs.insert(0, {
        'timestamp': datetime.now().strftime("%H:%M:%S.%f")[:-3],
        'agent': agent,
        'activity': activity
    })
    st.session_state.agent_logs = st.session_state.agent_logs[:15]

def log_agent_communication(title, data):
    """Log agent communication JSON"""
    if 'agent_communications' not in st.session_state:
        st.session_state.agent_communications = []
    
    st.session_state.agent_communications.insert(0, {
        'timestamp': datetime.now().strftime("%H:%M:%S.%f")[:-3],
        'title': title,
        'data': str(data)  # Ensure data is string
    })
    st.session_state.agent_communications = st.session_state.agent_communications[:10]

def display_agentcore_status():
    """Display AgentCore status"""
    agents = [
        {'name': '🎭 Orchestrator', 'status': 'running', 'color': '#dc3545'},
        {'name': '🔍 Vision', 'status': 'running', 'color': '#28a745'},
        {'name': '🧠 Analysis', 'status': 'running', 'color': '#fd7e14'},
        {'name': '📋 SOP', 'status': 'running', 'color': '#17a2b8'},
        {'name': '🤖 Action', 'status': 'running', 'color': '#ffc107'},
        {'name': '📡 Communication', 'status': 'running', 'color': '#6f42c1'}
    ]
    
    cols = st.columns(6)
    for i, agent in enumerate(agents):
        with cols[i]:
            st.markdown(f"""
            <div style="text-align: center; padding: 8px; border: 2px solid {agent['color']}; border-radius: 8px;">
                <h5>{agent['name']}</h5>
                <span style="color: {agent['color']};">● {agent['status'].upper()}</span>
            </div>
            """, unsafe_allow_html=True)
    
    st.info("🔒 All agents running in private VPC with AgentCore runtime")

def display_agent_logs():
    """Display agent execution logs"""
    if st.session_state.agent_logs:
        for log in st.session_state.agent_logs[:10]:
            agent_icons = {
                'vision': '🔍', 'sop': '📋', 'action': '🤖', 
                'communication': '📡', 'analysis': '🧠', 'system': '⚙️'
            }
            icon = agent_icons.get(log['agent'], '🤖')
            
            if 'error' in log['activity'].lower() or 'failed' in log['activity'].lower():
                st.error(f"{log['timestamp']} {icon} {log['agent'].title()}: {log['activity']}")
            else:
                st.text(f"{log['timestamp']} {icon} {log['agent'].title()}: {log['activity']}")
    else:
        st.info("No agent activity yet.")

def display_processing_history():
    """Display processing history"""
    if st.session_state.processing_history:
        for history in st.session_state.processing_history:
            with st.expander(f"🕐 {history['timestamp']} - {history['image']}"):
                result = history['result']
                
                if result.get('status') == 'success' and 'agentcore_results' in result:
                    agentcore_data = result['agentcore_results']
                    inspection_id = agentcore_data.get('inspection_id', 'N/A')
                    st.success(f"✅ AgentCore workflow completed: {inspection_id}")
                    
                    # Use shared defect parsing function
                    defects = parse_and_display_defects(agentcore_data)
                    
                    # Display recommendation
                    recommendation = agentcore_data.get('recommendation', 'REVIEW')
                    if recommendation == 'PASS':
                        st.success(f"📋 SOP: {recommendation}")
                    elif recommendation == 'FAIL':
                        st.error(f"📋 SOP: {recommendation}")
                    elif recommendation == 'REVIEW':
                        st.warning(f"📋 SOP: {recommendation} (requires manual inspection)")
                    else:
                        st.warning(f"📋 SOP: {recommendation}")
                    
                    # Show image with defect annotations if available
                    image_key = agentcore_data.get('image_key', '')
                    if image_key:
                        try:
                            bucket_name = discover_quality_inspection_bucket('us-east-1')
                            filename = image_key.split('/')[-1]
                            possible_keys = [f"defects/{filename}", f"processedimages/{filename}", image_key]
                            
                            for key in possible_keys:
                                try:
                                    image_bytes = download_s3_image(bucket_name, key, 'us-east-1')
                                    image = Image.open(io.BytesIO(image_bytes))
                                    
                                    # Annotate image with defects if any
                                    if defects:
                                        annotated_image = annotate_image_with_defects(image, defects)
                                        st.image(annotated_image, caption=f"🔴 {len(defects)} defect(s) detected with red bounding boxes", width=400)
                                        
                                        # Debug info
                                        st.info(f"**Debug:** Image: {key}, Size: {image.width}x{image.height}")
                                        for i, defect in enumerate(defects):
                                            coords = f"({defect.get('grid_x1')},{defect.get('grid_y1')}) to ({defect.get('grid_x2')},{defect.get('grid_y2')})"
                                            st.info(f"**Defect {i+1}:** {defect.get('type')} at grid {coords}")
                                    else:
                                        st.image(image, caption=f"✅ No defects detected", width=400)
                                    break
                                except:
                                    continue
                        except Exception as e:
                            st.info(f"Could not load image: {filename}")
                    
                    st.info("🤖 Action: File processed and moved")
                    st.info("📡 Communication: Results logged")
                    st.info("🧠 Analysis: Quality trends updated")
                        
                else:
                    st.error(f"❌ Workflow failed: {result.get('error', 'Unknown error')}")
    else:
        st.info("No processing history yet.")

def get_agentcore_logs(region):
    """Get recent AgentCore logs from CloudWatch"""
    try:
        logs_client = get_boto3_client('logs', region_name=region)
        
        # Get logs from all active AgentCore runtime log groups
        log_groups = [
            '/aws/bedrock-agentcore/runtimes/quality_inspection_orchestrator-d4T2R9GSN4-DEFAULT',
            '/aws/bedrock-agentcore/runtimes/quality_inspection_vision-sVDJ49CNIg-DEFAULT',
            '/aws/bedrock-agentcore/runtimes/quality_inspection_analysis-bQyboFGCNQ-DEFAULT',
            '/aws/bedrock-agentcore/runtimes/quality_inspection_sop-Fjy0Io9Tb9-DEFAULT',
            '/aws/bedrock-agentcore/runtimes/quality_inspection_action-BckwyVDqpt-DEFAULT',
            '/aws/bedrock-agentcore/runtimes/quality_inspection_communication-wbxeM4BU8B-DEFAULT'
        ]
        
        all_logs = []
        for log_group in log_groups:
            try:
                response = logs_client.filter_log_events(
                    logGroupName=log_group,
                    limit=10,
                    startTime=int((datetime.now().timestamp() - 3600) * 1000)  # Last 1 hour
                )
                
                for event in response.get('events', []):
                    # Extract agent name from log group
                    if 'orchestrator' in log_group:
                        agent_name = '🎭 Orchestrator'
                    elif 'vision' in log_group:
                        agent_name = '🔍 Vision'
                    elif 'analysis' in log_group:
                        agent_name = '🧠 Analysis'
                    elif 'sop' in log_group:
                        agent_name = '📋 SOP'
                    elif 'action' in log_group:
                        agent_name = '🤖 Action'
                    elif 'communication' in log_group:
                        agent_name = '📡 Communication'
                    else:
                        agent_name = 'Agent'
                    
                    all_logs.append({
                        'title': f'{agent_name} Runtime',
                        'message': event['message'],
                        'timestamp': event['timestamp']
                    })
            except Exception as e:
                # Skip log groups that don't exist or have no recent logs
                continue
        
        # Sort by timestamp, most recent first
        all_logs.sort(key=lambda x: x['timestamp'], reverse=True)
        return all_logs[:15]  # Return last 15 log entries
        
    except Exception as e:
        return []

def get_all_recent_results(region):
    """Get all recent processing results from DynamoDB"""
    try:
        dynamodb = get_boto3_resource('dynamodb', region_name=region)
        table = dynamodb.Table('vision-inspection-data')
        
        # Get all results and sort by timestamp
        response = table.scan()
        
        if response['Items']:
            # Sort by timestamp, most recent first
            items = sorted(response['Items'], key=lambda x: x.get('timestamp', ''), reverse=True)
            return items
        
        return []
    except Exception as e:
        st.error(f"Error getting results: {str(e)}")
        return []

def monitor_agentcore_results(s3_key, region, max_wait=30):
    """Monitor DynamoDB for AgentCore results"""
    try:
        dynamodb = get_boto3_resource('dynamodb', region_name=region)
        table = dynamodb.Table('vision-inspection-data')
        
        filename = s3_key.split('/')[-1]
        
        # Search by image_key field (not image_url)
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('image_key').contains(filename)
        )
        
        if response['Items']:
            # Return most recent result (sort by timestamp)
            items = sorted(response['Items'], key=lambda x: x.get('timestamp', ''), reverse=True)
            return items[0]
        
        return None
    except Exception as e:
        st.error(f"Error monitoring results: {str(e)}")
        return None

def parse_and_display_defects(agentcore_data):
    """Shared function to parse and display defects from AgentCore data"""
    defects = []
    
    if agentcore_data.get('defect_detected') == 'Y':
        st.error("🔍 Vision: Defects detected")
        
        # First try to get defects from structured array
        if 'defects' in agentcore_data and agentcore_data['defects']:
            defects = agentcore_data['defects']
            # Convert string coordinates to integers if needed
            for defect in defects:
                for coord_key in ['grid_x1', 'grid_y1', 'grid_x2', 'grid_y2']:
                    if coord_key in defect and isinstance(defect[coord_key], str):
                        defect[coord_key] = int(defect[coord_key])
            
            # Show defect details
            for i, defect in enumerate(defects, 1):
                st.warning(f"**Defect {i}:** {defect.get('type', 'Unknown')}")
                st.warning(f"**Description:** {defect.get('description', 'No description')}")
                if all(k in defect for k in ['grid_x1', 'grid_y1', 'grid_x2', 'grid_y2']):
                    st.info(f"**Grid Location:** ({defect['grid_x1']},{defect['grid_y1']}) to ({defect['grid_x2']},{defect['grid_y2']})")
            st.info(f"**Confidence:** {agentcore_data.get('confidence', 'N/A')}%")
        else:
            st.warning("Defects detected but no structured defect data found")
    elif agentcore_data.get('defect_detected') == 'N':
        st.success("🔍 Vision: No defects detected")
    else:
        st.warning("🔍 Vision: Unknown status")
    
    return defects

def display_agentcore_results(result):
    """Display AgentCore results from DynamoDB"""
    st.subheader("🤖 AgentCore Results")
    
    # Use shared defect parsing function
    defects = parse_and_display_defects(result)
    
    # Store defects for image annotation
    st.session_state.agentcore_defects = defects
    
    if 'disposition' in result:
        st.info(f"📋 SOP: {result['disposition']}")
    elif 'recommendation' in result:
        st.info(f"📋 SOP: {result['recommendation']}")
    
    if 'action_taken' in result:
        st.info(f"🤖 Action: {result['action_taken']}")
    
    st.success("📡 Communication: Notifications sent")
    st.success("🧠 Analysis: Trends updated")

def display_workflow_results(result):
    """Display workflow results"""
    if result.get('status') == 'triggered':
        workflow_id = result.get('workflow_id', result.get('inspection_id', 'N/A'))
        st.success(f"✅ AgentCore Workflow Triggered: {workflow_id}")
        st.info("🔄 Processing with private VPC agents...")
        st.info("📋 Check results below or refresh page for updates")
    elif result.get('status') == 'success':
        workflow_id = result.get('workflow_id', result.get('inspection_id', 'N/A'))
        st.success(f"✅ Modular Workflow Completed: {workflow_id}")
        
        if 'vision' in result:
            vision = result['vision']
            if vision.get('defect_detected') == 'Y':
                defects = vision.get('defects', [])
                with st.container():
                    st.error(f"🔍 Vision: {len(defects)} defects detected")
                    st.warning("**Defect Details:**")
                    for defect in defects:
                        st.warning(f"• {defect.get('type', 'Unknown')}: {defect.get('description', 'No description')}")
            else:
                st.success("🔍 Vision: No defects detected")
        
        if 'sop' in result:
            sop = result['sop']
            disposition = sop.get('disposition', 'N/A')
            sop_rule = sop.get('sop_rule', 'N/A')
            st.info(f"📋 SOP: {disposition} ({sop_rule})")
        
        if 'action' in result:
            action = result['action']
            action_type = action.get('physical_action', action.get('action', 'N/A'))
            st.info(f"🤖 Action: {action_type}")
        
        if 'communication' in result:
            st.info(f"📡 Communication: Updates and alerts sent")
        
        if 'analysis' in result:
            st.info("🧠 Analysis: Trends recorded and predictions updated")
            
    else:
        st.error(f"❌ Workflow failed: {result.get('error')}")

def display_agent_communications():
    """Display agent communications from CloudWatch logs"""
    try:
        # Get recent AgentCore logs
        agentcore_logs = get_agentcore_logs('us-east-1')
        
        if agentcore_logs:
            st.info(f"Showing last {min(len(agentcore_logs), 10)} agent communications from CloudWatch logs")
            for log_entry in agentcore_logs[:10]:
                # Format timestamp
                try:
                    timestamp = datetime.fromtimestamp(log_entry['timestamp'] / 1000).strftime("%H:%M:%S")
                except:
                    timestamp = "Unknown"
                
                title = log_entry['title']
                message = log_entry['message']
                
                # Check if message contains JSON-like content
                if '{' in message and '}' in message:
                    with st.expander(f"🕰️ {timestamp} - {title} (JSON)"):
                        # Try to extract and format JSON
                        try:
                            start = message.find('{')
                            end = message.rfind('}') + 1
                            if start != -1 and end > start:
                                json_str = message[start:end]
                                parsed_json = json.loads(json_str)
                                st.code(json.dumps(parsed_json, indent=2), language='json')
                            else:
                                st.code(message, language='text')
                        except:
                            st.code(message, language='text')
                else:
                    with st.expander(f"🕰️ {timestamp} - {title}"):
                        st.text(message)
        else:
            st.info("No agent communications found in CloudWatch logs.")
    except Exception as e:
        st.error(f"Could not load agent communications: {str(e)}")

def discover_quality_inspection_bucket(region):
    """Auto-discover the quality inspection S3 bucket name"""
    try:
        # Method 1: Check CloudFormation stacks for bucket outputs
        cf = get_boto3_client('cloudformation', region_name=region)
        stacks = ['QualityInspectionStack', 'AgenticQualityInspectionStack', 'MA3TMainStack']
        
        for stack_name in stacks:
            try:
                response = cf.describe_stacks(StackName=stack_name)
                outputs = response['Stacks'][0].get('Outputs', [])
                for output in outputs:
                    key = output['OutputKey'].lower()
                    if any(word in key for word in ['bucket', 'machinepartimages', 'resourcebucket']):
                        bucket_name = output['OutputValue']
                        # Verify bucket exists and has expected structure
                        if verify_quality_inspection_bucket(bucket_name, region):
                            return bucket_name
            except:
                continue
        
        # Method 2: Search all S3 buckets for quality inspection structure
        s3 = get_boto3_client('s3', region_name=region)
        response = s3.list_buckets()
        
        for bucket in response['Buckets']:
            bucket_name = bucket['Name']
            # Check for quality inspection bucket patterns
            if any(pattern in bucket_name.lower() for pattern in ['machinepartimages', 'quality', 'inspection']):
                if verify_quality_inspection_bucket(bucket_name, region):
                    return bucket_name
        
        # Method 3: Search for bucket with qualityinspectionstack prefix
        for bucket in response['Buckets']:
            bucket_name = bucket['Name']
            if bucket_name.startswith('qualityinspectionstack-machinepartimages'):
                if verify_quality_inspection_bucket(bucket_name, region):
                    return bucket_name
        
        # Method 4: Fallback to account-based naming
        sts = get_boto3_client('sts')
        account_id = sts.get_caller_identity()['Account']
        fallback_name = f"machinepartimages-{account_id}"
        
        # Check if fallback exists
        try:
            s3.head_bucket(Bucket=fallback_name)
            return fallback_name
        except:
            pass
        
        # If nothing found, return the fallback anyway (will show error in UI)
        return fallback_name
        
    except Exception as e:
        # Ultimate fallback
        return "machinepartimages"

def verify_quality_inspection_bucket(bucket_name, region):
    """Verify bucket exists and has quality inspection structure"""
    try:
        s3 = get_boto3_client('s3', region_name=region)
        
        # Check if bucket exists
        s3.head_bucket(Bucket=bucket_name)
        
        # Check for expected folder structure or reference image
        try:
            # Look for cleanimages folder or reference image
            response = s3.list_objects_v2(Bucket=bucket_name, Prefix='cleanimages/', MaxKeys=1)
            if response.get('Contents'):
                return True
            
            # Look for inputimages folder
            response = s3.list_objects_v2(Bucket=bucket_name, Prefix='inputimages/', MaxKeys=1)
            if response.get('Contents'):
                return True
            
            # If no specific folders, but bucket exists, it might be new
            return True
            
        except:
            # Bucket exists but might be empty - still valid
            return True
            
    except:
        return False

# Helper functions
def cleanup_temp_images():
    """Clean up temporary image files"""
    if hasattr(st.session_state, 'temp_image_path') and st.session_state.temp_image_path:
        try:
            if os.path.exists(st.session_state.temp_image_path):
                os.remove(st.session_state.temp_image_path)
        except:
            pass
        st.session_state.temp_image_path = None

def store_image_locally(image_bytes, filename):
    """Store image locally and return path"""
    cleanup_temp_images()  # Clean up previous image
    
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"streamlit_temp_{filename}")
    
    with open(temp_path, 'wb') as f:
        f.write(image_bytes)
    
    st.session_state.temp_image_path = temp_path
    return temp_path

def annotate_image_with_defects(image, defects):
    """Draw red bounding boxes around defects on image"""
    if not defects:
        return image
    
    # Create a copy to avoid modifying original
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    
    for defect in defects:
        # Check for grid coordinates first
        if all(key in defect for key in ['grid_x1', 'grid_y1', 'grid_x2', 'grid_y2']):
            # Convert coordinates to integers (handle Decimal types from DynamoDB)
            grid_x1 = int(float(defect['grid_x1']))
            grid_y1 = int(float(defect['grid_y1']))
            grid_x2 = int(float(defect['grid_x2']))
            grid_y2 = int(float(defect['grid_y2']))
            
            # Convert grid coordinates (1-10 scale) to pixel coordinates
            # Vision agent uses 1-based coordinates: (1,1) to (10,10)
            grid_width = float(image.width) / 10.0
            grid_height = float(image.height) / 10.0
            
            # Map 1-based grid coordinates to 0-based pixel coordinates
            x1 = int((grid_x1 - 1) * grid_width)
            y1 = int((grid_y1 - 1) * grid_height)
            x2 = int((grid_x2) * grid_width)  # grid_x2 is inclusive, so don't subtract 1
            y2 = int((grid_y2) * grid_height)  # grid_y2 is inclusive, so don't subtract 1
            
            # Ensure coordinates are valid and make box visible
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            
            # Make sure box has minimum size for visibility
            if x2 - x1 < 20:
                x2 = x1 + 20
            if y2 - y1 < 20:
                y2 = y1 + 20
            
            # Ensure coordinates don't exceed image bounds
            x1 = max(0, min(x1, image.width - 1))
            y1 = max(0, min(y1, image.height - 1))
            x2 = max(x1 + 1, min(x2, image.width))
            y2 = max(y1 + 1, min(y2, image.height))
            
            # Draw red bounding box with better visibility
            draw.rectangle([x1, y1, x2, y2], outline='red', width=6)
            # Add inner white border for contrast
            draw.rectangle([x1+2, y1+2, x2-2, y2-2], outline='white', width=2)
            
            # Add coordinate labels for debugging
            try:
                draw.text((x1+2, y1+2), f"({x1},{y1})", fill='yellow')
                draw.text((x2-50, y2-15), f"({x2},{y2})", fill='yellow')
            except:
                pass
            
        # Fallback to direct pixel coordinates
        elif all(key in defect for key in ['bbox_x1', 'bbox_y1', 'bbox_x2', 'bbox_y2']):
            x1 = int(float(defect['bbox_x1']))
            y1 = int(float(defect['bbox_y1']))
            x2 = int(float(defect['bbox_x2']))
            y2 = int(float(defect['bbox_y2']))
            
            # Draw red bounding box with better visibility
            draw.rectangle([x1, y1, x2, y2], outline='red', width=6)
            # Add inner white border for contrast
            draw.rectangle([x1+2, y1+2, x2-2, y2-2], outline='white', width=2)
    
    return annotated

def get_s3_objects(bucket_name, prefix, region):
    """Get list of objects in S3 bucket with given prefix"""
    try:
        s3 = get_boto3_client('s3', region_name=region)
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        if 'Contents' in response:
            # Sort by last modified time, most recent first
            objects = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
            return [obj['Key'] for obj in objects if obj['Key'] != prefix]
        return []
    except:
        return []

def upload_file_to_s3(uploaded_file, bucket_name, region):
    """Upload file to S3 inputimages folder"""
    try:
        s3 = get_boto3_client('s3', region_name=region)
        s3_key = f"inputimages/{uploaded_file.name}"
        s3.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=uploaded_file.getvalue(),
            ContentType=uploaded_file.type
        )
        return {'success': True, 'key': s3_key}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def download_s3_image(bucket_name, s3_key, region):
    s3 = get_boto3_client('s3', region_name=region)
    response = s3.get_object(Bucket=bucket_name, Key=s3_key)
    return response['Body'].read()

def encode_image_bytes(image_bytes):
    return base64.b64encode(image_bytes).decode('utf-8')

def detect_defects_nova_direct(test_image_base64, ref_image_base64):
    """Direct Nova Pro defect detection with images"""
    bedrock = get_boto3_client('bedrock-runtime', region_name='us-east-1')
    
    prompt = """CRITICAL: Compare these manufacturing parts carefully. First image is CLEAN REFERENCE, second is TEST IMAGE.

METHOD: Imagine the TEST image divided into a 10x10 grid (100 squares total).
- Grid coordinates: (0,0) = top-left, (9,9) = bottom-right
- Each grid cell represents 1/10th of image width/height

STEPS:
1. Study the REFERENCE image to understand normal appearance
2. Compare TEST image against REFERENCE
3. Identify defects that appear in TEST but NOT in REFERENCE
4. Determine which grid cells contain each defect
5. Convert grid coordinates to approximate pixel positions

Respond ONLY with JSON:
{
  "defect_detected": "Y" or "N",
  "defects": [
    {
      "type": "Crack" or "Scratch",
      "length_mm": number,
      "description": "defect description and location",
      "grid_x1": leftmost_grid_column_0_to_9,
      "grid_y1": topmost_grid_row_0_to_9,
      "grid_x2": rightmost_grid_column_0_to_9,
      "grid_y2": bottommost_grid_row_0_to_9
    }
  ],
  "confidence": percentage,
  "analysis_summary": "brief summary"
}

EXAMPLE: If defect spans from grid cell (2,3) to (4,5), use grid_x1:2, grid_y1:3, grid_x2:4, grid_y2:5"""
    
    content = [
        {"text": prompt},
        {"image": {"format": "jpeg", "source": {"bytes": ref_image_base64}}},
        {"image": {"format": "jpeg", "source": {"bytes": test_image_base64}}}
    ]

    body = {
        "messages": [{"role": "user", "content": content}],
        "inferenceConfig": {"temperature": 0.1}
    }
    
    try:
        response = bedrock.invoke_model(
            modelId="amazon.nova-pro-v1:0",
            body=json.dumps(body)
        )
        
        result = json.loads(response['body'].read())
        content = result['output']['message']['content'][0]['text']
        
        # Parse JSON from response
        start = content.find('{')
        end = content.rfind('}') + 1
        if start != -1 and end != 0:
            json_str = content[start:end]
            return json.loads(json_str)
        
        return {"error": "Could not parse Nova Pro response"}
        
    except Exception as e:
        return {"error": f"Nova Pro error: {str(e)}"}

def send_sns_alert(filename, vision_data, region):
    """Send SNS alert for defects"""
    try:
        import yaml
        with open('config/settings.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        sns = get_boto3_client('sns', region_name=region)
        topic_arn = config['aws']['sns_topic_arn']
        
        defects = vision_data.get('defects', [])
        message = f"""QUALITY ALERT: Defects Detected

Product: {filename}
Defects Found: {len(defects)}

Defect Details:
{json.dumps(defects, indent=2)}

Action Required: Review and disposition
Timestamp: {datetime.now().isoformat()}"""
        
        sns.publish(
            TopicArn=topic_arn,
            Subject=f'Quality Alert: {filename}',
            Message=message
        )
        log_agent_activity("sns", f"Alert sent for {filename}")
    except Exception as e:
        log_agent_activity("sns", f"Alert failed: {str(e)}")

if __name__ == "__main__":
    # Parse command line arguments for AWS profile
    parser = argparse.ArgumentParser(description='Quality Inspection Streamlit App')
    parser.add_argument('--profile', help='AWS profile to use', default=None)
    
    # Parse known args to avoid conflicts with Streamlit
    args, unknown = parser.parse_known_args()
    
    # Set global AWS profile
    if args.profile:
        AWS_PROFILE = args.profile
        st.sidebar.info(f"Using AWS Profile: {AWS_PROFILE}")
    else:
        st.sidebar.info("Using default AWS profile")
    
    main()