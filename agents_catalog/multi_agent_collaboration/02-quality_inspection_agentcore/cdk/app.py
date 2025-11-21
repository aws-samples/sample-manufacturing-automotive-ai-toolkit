#!/usr/bin/env python3
import aws_cdk as cdk
import os
from quality_inspection_stack import QualityInspectionStack
from quality_inspection_streamlit_demo_stack import QualityInspectionStreamlitDemoStack

app = cdk.App()

# Use current AWS account and region from profile/environment
# This makes the stack deployable to any account
env = cdk.Environment(
    account=os.environ.get('CDK_DEFAULT_ACCOUNT'),
    region=os.environ.get('CDK_DEFAULT_REGION', 'us-east-1')
)

# Main infrastructure stack
main_stack = QualityInspectionStack(app, "AgenticQualityInspectionStack", env=env)

# Streamlit demo stack (depends on main stack for VPC)
streamlit_stack = QualityInspectionStreamlitDemoStack(
    app, "QualityInspectionStreamlitDemoStack", 
    env=env
)
streamlit_stack.add_dependency(main_stack)

app.synth()