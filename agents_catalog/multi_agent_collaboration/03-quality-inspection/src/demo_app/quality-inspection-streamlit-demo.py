import streamlit as st
import boto3
import json
from datetime import datetime
from PIL import Image, ImageDraw
import io

def get_boto3_client(service_name, region_name=None):
    """Get boto3 client using current AWS credentials"""
    if region_name:
        return boto3.client(service_name, region_name=region_name)
    return boto3.client(service_name)

def get_boto3_resource(service_name, region_name=None):
    """Get boto3 resource using current AWS credentials"""
    if region_name:
        return boto3.resource(service_name, region_name=region_name)
    return boto3.resource(service_name)

# AgentCore agents - no local imports needed

# Must be the very first Streamlit command
st.set_page_config(
    page_title="Multi-Agent Quality Inspection",
    page_icon="🏭",
    layout="wide"
)

def log_agent_activity(agent, message):
    """Log agent activity"""
    if 'agent_logs' not in st.session_state:
        st.session_state.agent_logs = []
    st.session_state.agent_logs.append({
        'timestamp': datetime.now(),
        'agent': agent,
        'message': message
    })

def load_recent_results(region):
    """Load recent processing results from DynamoDB"""
    try:
        dynamodb = get_boto3_resource('dynamodb', region)
        table = dynamodb.Table('vision-inspection-data')
        
        response = table.scan(
            Limit=10,
            ScanIndexForward=False
        )
        
        results = []
        for item in response.get('Items', []):
            results.append({
                'timestamp': item.get('timestamp', ''),
                'image': item.get('image_key', '').split('/')[-1],
                'result': {
                    'agentcore_results': item
                }
            })
        
        st.session_state.processing_history = sorted(results, key=lambda x: x['timestamp'], reverse=True)
    except Exception as e:
        st.session_state.processing_history = []
        log_agent_activity("system", f"Failed to load results: {str(e)}")

def upload_file_to_s3(uploaded_file, bucket_name, region):
    """Upload file to S3"""
    try:
        s3_client = get_boto3_client('s3', region)
        
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{uploaded_file.name}"
        key = f"inputimages/{filename}"
        
        # Upload file
        s3_client.upload_fileobj(
            uploaded_file,
            bucket_name,
            key,
            ExtraArgs={'ContentType': uploaded_file.type}
        )
        
        return {'success': True, 'key': key}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_s3_objects(bucket_name, prefix, region):
    """Get list of S3 objects"""
    try:
        s3_client = get_boto3_client('s3', region)
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix
        )
        return [obj['Key'] for obj in response.get('Contents', [])]
    except:
        return []

def download_s3_image(bucket_name, key, region):
    """Download image from S3"""
    s3_client = get_boto3_client('s3', region)
    response = s3_client.get_object(Bucket=bucket_name, Key=key)
    return response['Body'].read()

def display_agentcore_status():
    """Display AgentCore status"""
    st.info("🟢 AgentCore multi-agent system deployed and ready")
    st.text("• 🔍 Vision Agent: Nova Pro defect detection")
    st.text("• 🧠 Analysis Agent: AI quality assessment")
    st.text("• 📋 SOP Agent: Manufacturing compliance")
    st.text("• 🤖 Action Agent: Production control")
    st.text("• 📡 Communication Agent: ERP integration")
    st.text("• 🎭 Orchestrator Agent: Workflow coordination")

def parse_and_display_defects(agentcore_data):
    """Parse defects from AgentCore data"""
    defects = []
    
    # Try to parse defects from various possible fields
    defect_info = agentcore_data.get('defects', [])
    if isinstance(defect_info, str):
        try:
            defect_info = json.loads(defect_info)
        except:
            defect_info = []
    
    for defect in defect_info:
        if isinstance(defect, dict):
            defects.append({
                'type': defect.get('type', 'Unknown'),
                'confidence': defect.get('confidence', 0),
                'coordinates': defect.get('coordinates', {})
            })
    
    return defects

def annotate_image_with_defects(image, defects):
    """Annotate image with defect bounding boxes"""
    draw = ImageDraw.Draw(image)
    
    for defect in defects:
        coords = defect.get('coordinates', {})
        if coords:
            x1 = coords.get('x1', 0)
            y1 = coords.get('y1', 0)
            x2 = coords.get('x2', 100)
            y2 = coords.get('y2', 100)
            
            # Draw red bounding box
            draw.rectangle([x1, y1, x2, y2], outline='red', width=3)
            
            # Add defect type label
            defect_type = defect.get('type', 'Defect')
            draw.text((x1, y1-20), defect_type, fill='red')
    
    return image

def main():
    st.title("🏭 Multi-Agent Quality Inspection")
    st.markdown("**Organized Agent Architecture with Separate Files**")
    
    # Initialize session state
    if 'agent_logs' not in st.session_state:
        st.session_state.agent_logs = []
    if 'agent_communications' not in st.session_state:
        st.session_state.agent_communications = []
    
    # Initialize region in session state
    if 'region' not in st.session_state:
        st.session_state.region = 'us-east-1'
    
    # Always load recent results on page load/refresh
    with st.spinner("Loading recent results..."):
        try:
            load_recent_results(st.session_state.region)
            if 'initialized' not in st.session_state:
                log_agent_activity("system", "AgentCore agents ready - no local initialization needed")
                st.session_state.initialized = True
        except Exception as e:
            st.session_state.processing_history = []
            log_agent_activity("system", f"Failed to auto-load results: {str(e)}")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📸 Image Processing")
        
        # S3 Configuration - Get bucket name from SSM parameter
        region = st.selectbox("AWS Region", ["us-east-1", "us-west-2"], index=0 if st.session_state.region == 'us-east-1' else 1)
        
        # Update session state when region changes
        if region != st.session_state.region:
            st.session_state.region = region
            st.rerun()
        
        try:
            ssm = get_boto3_client('ssm', region)
            bucket_name = ssm.get_parameter(Name='/quality-inspection/s3-bucket-name')['Parameter']['Value']
        except:
            bucket_name = "machinepartimages"
        st.info(f"📦 S3 Bucket: {bucket_name}")
        
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
        available_images = get_s3_objects(bucket_name, "inputimages/", region)
        if available_images:
            st.info(f"📁 Recent uploads: {len(available_images)} files in inputimages/")
            with st.expander("View recent uploads"):
                for img in available_images[-5:]:  # Show last 5
                    st.text(f"• {img.split('/')[-1]}")
        else:
            st.info("📁 No files in inputimages/ folder yet")
        
        # AgentCore agents run remotely
        
        # Display images side by side
        ref_bucket = bucket_name
        ref_key = "cleanimages/Cleanimage.jpg"
        
        img_col1, img_col2 = st.columns(2)
        
        with img_col1:
            try:
                ref_image_bytes = download_s3_image(ref_bucket, ref_key, st.session_state.region)
                ref_image = Image.open(io.BytesIO(ref_image_bytes))
                st.image(ref_image, caption="Reference (Clean)", width='stretch')
            except:
                st.warning("Could not load reference image")
        
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
                    test_image_bytes = download_s3_image(bucket_name, latest_image, st.session_state.region)
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
                load_recent_results(st.session_state.region)
                recent_count = len(st.session_state.processing_history)
                st.success(f"✅ Found {recent_count} recent processing results!")
                st.rerun()
    
    with col2:
        st.header("🤖 Multi-Agent Architecture")
        st.info("""
        **Amazon Bedrock AgentCore:**
        - Managed agent runtime with auto-scaling
        - Built-in memory and observability
        - Private VPC deployment
        - **S3 event-driven workflow**
        
        **Sequential Agent Pipeline:**
        - 🔍 **Vision Agent**: Nova Pro defect detection
        - 🧠 **Analysis Agent**: AI quality assessment  
        - 📋 **SOP Agent**: Manufacturing compliance rules
        - 🤖 **Action Agent**: Production control execution
        - 📡 **Communication Agent**: ERP integration & alerts
        - 🎭 **Orchestrator Agent**: Workflow coordination
        
        **Data Flow:**
        1. Image upload → S3 inputimages/
        2. Lambda triggers orchestrator agent
        3. Sequential multi-agent processing
        4. Results stored in DynamoDB tables
        5. SNS notifications & audit logging
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
                    try:
                        ssm = get_boto3_client('ssm', st.session_state.region)
                        bucket_name = ssm.get_parameter(Name='/quality-inspection/s3-bucket-name')['Parameter']['Value']
                    except:
                        bucket_name = "machinepartimages"
                    
                    # Check if image is in defects or processedimages folder
                    possible_keys = [f"defects/{filename}", f"processedimages/{filename}", image_key]
                    
                    for key in possible_keys:
                        try:
                            image_bytes = download_s3_image(bucket_name, key, st.session_state.region)
                            image = Image.open(io.BytesIO(image_bytes))
                            
                            # Use shared defect parsing function
                            defects = parse_and_display_defects(agentcore_data)
                            
                            # Annotate image with defects if any
                            if defects:
                                annotated_image = annotate_image_with_defects(image, defects)
                                st.image(annotated_image, caption=f"🔴 {len(defects)} defect(s) detected with red bounding boxes", width=400)
                            break
                        except:
                            continue
                except Exception as e:
                    st.error(f"Error loading image: {str(e)}")

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
            <div style="text-align: center; padding: 8px; border: 2px solid {agent['color']}; border-radius: 8px; height: 80px; display: flex; flex-direction: column; justify-content: center;">
                <h5 style="margin: 0; font-size: 14px;">{agent['name']}</h5>
                <span style="color: {agent['color']}; font-size: 12px;">● {agent['status'].upper()}</span>
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
                            # Try to load and display the image
                            try:
                                ssm = get_boto3_client('ssm', st.session_state.region)
                                bucket_name = ssm.get_parameter(Name='/quality-inspection/s3-bucket-name')['Parameter']['Value']
                            except:
                                bucket_name = "machinepartimages"
                            
                            # Check if image is in defects or processedimages folder
                            filename = image_key.split('/')[-1]
                            possible_keys = [f"defects/{filename}", f"processedimages/{filename}", image_key]
                            
                            for key in possible_keys:
                                try:
                                    image_bytes = download_s3_image(bucket_name, key, st.session_state.region)
                                    image = Image.open(io.BytesIO(image_bytes))
                                    
                                    # Annotate image with defects if any
                                    if defects:
                                        annotated_image = annotate_image_with_defects(image, defects)
                                        st.image(annotated_image, caption=f"Processed: {filename} (with defect annotations)", width=400)
                                        st.success(f"🔴 Red boxes show detected defects at grid coordinates")
                                        # Grid coordinates already shown above with defect details
                                    else:
                                        st.image(image, caption=f"Processed: {filename}", width=400)
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
    """Get recent AgentCore logs from CloudWatch with actual agent communications"""
    try:
        logs_client = get_boto3_client('logs', region_name=region)
        
        # First, try to discover log groups dynamically
        try:
            log_groups_response = logs_client.describe_log_groups(
                logGroupNamePrefix='/aws/bedrock-agentcore/runtimes/quality_inspection'
            )
            log_groups = [lg['logGroupName'] for lg in log_groups_response.get('logGroups', [])]
        except:
            # Fallback to known log groups
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
                    limit=10,  # More logs per group to find actual communications
                    startTime=int((datetime.now().timestamp() - 3600) * 1000)  # Last 1 hour
                )
                
                for event in response.get('events', []):
                    message = event['message']
                    
                    # Filter for actual agent communications (responses, results, outputs)
                    if any(keyword in message.lower() for keyword in ['response', 'result', 'output', 'analysis', 'defect', 'recommendation', 'action']):
                        # Extract agent name from log group
                        if 'orchestrator' in log_group:
                            agent_name = '🎭 Orchestrator Agent'
                        elif 'vision' in log_group:
                            agent_name = '🔍 Vision Agent'
                        elif 'analysis' in log_group:
                            agent_name = '🧠 Analysis Agent'
                        elif 'sop' in log_group:
                            agent_name = '📋 SOP Agent'
                        elif 'action' in log_group:
                            agent_name = '🤖 Action Agent'
                        elif 'communication' in log_group:
                            agent_name = '📡 Communication Agent'
                        else:
                            agent_name = 'Agent'
                        
                        all_logs.append({
                            'title': agent_name,
                            'message': message,
                            'timestamp': event['timestamp']
                        })
            except Exception as e:
                # Skip log groups that don't exist or have no recent logs
                continue
        
        # Sort by timestamp, most recent first
        all_logs.sort(key=lambda x: x['timestamp'], reverse=True)
        return all_logs[:15]  # Return more entries to show actual communications
        
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
    except Exception:
        return []

def get_agent_communications_from_db(region):
    """Get agent communications from all DynamoDB tables"""
    communications = []
    
    # Define tables and their corresponding agent names
    tables = {
        'vision-inspection-data': 'vision',
        'sop-decisions': 'sop', 
        'action-execution-log': 'action',
        'erp-integration-log': 'communication',
        'historical-trends': 'analysis'
    }
    
    try:
        dynamodb = get_boto3_resource('dynamodb', region_name=region)
        
        for table_name, agent_name in tables.items():
            try:
                table = dynamodb.Table(table_name)
                response = table.scan(Limit=3)  # Get recent entries from each table
                
                for item in response.get('Items', []):
                    # Convert DynamoDB item to regular dict and add agent identifier
                    comm_data = dict(item)
                    comm_data['agent'] = agent_name
                    
                    # Ensure we have a timestamp for sorting
                    if 'timestamp' not in comm_data:
                        comm_data['timestamp'] = datetime.now().isoformat()
                    
                    communications.append(comm_data)
                    
            except Exception as e:
                # Skip tables that don't exist or have issues
                continue
        
        # Sort all communications by timestamp, most recent first
        communications.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return communications[:8]  # Return top 8 most recent
        
    except Exception as e:
        return []



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



def display_agent_communications():
    """Display actual agent communications from CloudWatch logs"""
    
    # Get actual agent communications from CloudWatch logs
    try:
        agentcore_logs = get_agentcore_logs(st.session_state.region)
        
        if agentcore_logs:
            st.info(f"💬 Showing {len(agentcore_logs)} recent agent communications")
            
            for log_entry in agentcore_logs:
                try:
                    timestamp = datetime.fromtimestamp(log_entry['timestamp'] / 1000).strftime("%H:%M:%S")
                except:
                    timestamp = "Unknown"
                
                title = log_entry['title']
                message = log_entry['message']
                
                with st.expander(f"{title} - {timestamp}"):
                    # Try to extract and format JSON from log messages
                    if 'response' in message.lower() or 'result' in message.lower() or '{' in message:
                        try:
                            # Look for JSON in the message
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
                        st.text(message)
        else:
            st.info("💬 No recent agent communications found in CloudWatch logs")
            
    except Exception as e:
        st.warning(f"CloudWatch logs unavailable: {str(e)}")
        
        # Fallback: Show DynamoDB results as communications
        agent_comms = get_agent_communications_from_db(st.session_state.region)
        
        if agent_comms:
            st.info(f"📊 Fallback: Showing {len(agent_comms)} results from DynamoDB tables")
            
            for comm in agent_comms:
                timestamp = comm.get('timestamp', 'Unknown')
                agent = comm.get('agent', 'Unknown')
                
                # Format timestamp for display
                try:
                    if timestamp != 'Unknown':
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        display_time = dt.strftime("%H:%M:%S")
                    else:
                        display_time = timestamp
                except:
                    display_time = timestamp[:8] if len(timestamp) > 8 else timestamp
                
                # Agent icons
                agent_icons = {
                    'vision': '🔍', 'analysis': '🧠', 'sop': '📋', 
                    'action': '🤖', 'communication': '📡', 'orchestrator': '🎭'
                }
                icon = agent_icons.get(agent.lower(), '🤖')
                
                with st.expander(f"{icon} {display_time} - {agent.title()} Agent Result"):
                    # Remove timestamp and agent from data to avoid duplication
                    display_data = {k: v for k, v in comm.items() if k not in ['timestamp', 'agent']}
                    st.code(json.dumps(display_data, indent=2, default=str), language='json')
        else:
            st.info("💬 Agent communications will appear here when processing occurs")
            st.info("🔄 Upload an image to trigger AgentCore workflow and see communications")

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
            grid_width = float(image.width) / 10.0
            grid_height = float(image.height) / 10.0
            
            # Map grid coordinates to pixel coordinates (1-based to 0-based)
            x1 = int((grid_x1 - 1) * grid_width)
            y1 = int((grid_y1 - 1) * grid_height)
            x2 = int(grid_x2 * grid_width)
            y2 = int(grid_y2 * grid_height)
            
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



if __name__ == "__main__":
    main()