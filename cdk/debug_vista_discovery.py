#!/usr/bin/env python3
"""
Debug Vista agents discovery
"""

import sys
import os
sys.path.insert(0, '.')

from stacks.nested_stack_registry import AgentRegistry
import aws_cdk as cdk

def debug_vista_discovery():
    # Create a minimal test stack
    app = cdk.App()
    stack = cdk.Stack(app, 'TestStack')
    registry = AgentRegistry(stack)

    # Test Vista agents detection specifically
    vista_path = '../agents_catalog/multi_agent_collaboration/00-vista-agents'
    print(f'Vista path: {vista_path}')
    print(f'Vista path exists: {os.path.exists(vista_path)}')

    cdk_config = registry._detect_cdk_stack('00-vista-agents', vista_path, 'multi_agent_collaboration')
    print(f'CDK config result: {cdk_config}')

    if cdk_config:
        print(f'CDK config details: {cdk_config.__dict__}')
    else:
        # Debug why it failed
        cdk_path = os.path.join(vista_path, 'cdk')
        app_py_path = os.path.join(cdk_path, 'app.py')
        print(f'CDK path: {cdk_path}')
        print(f'CDK path exists: {os.path.exists(cdk_path)}')
        print(f'app.py path: {app_py_path}')
        print(f'app.py exists: {os.path.exists(app_py_path)}')
        
        if os.path.exists(app_py_path):
            stack_class = registry._extract_stack_class_name(app_py_path, '00-vista-agents')
            print(f'Extracted stack class: {stack_class}')

if __name__ == "__main__":
    debug_vista_discovery()