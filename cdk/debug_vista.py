#!/usr/bin/env python3
"""
Debug Vista agents discovery specifically
"""

import sys
import os

# Add the cdk directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Starting Vista agents debug test...")

try:
    from stacks.nested_stack_registry import AgentRegistry
    
    # Create a minimal registry without a full stack
    class MockStack:
        def __init__(self):
            self.stack_name = "TestStack"
            self.region = "us-east-1"
            self.account = "123456789012"
    
    mock_stack = MockStack()
    registry = AgentRegistry(mock_stack)
    
    # Test Vista agents discovery step by step
    agent_name = '00-vista-agents'
    category = 'multi_agent_collaboration'
    
    # Get the workspace root path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(current_dir)
    agents_catalog_path = os.path.join(workspace_root, "agents_catalog")
    agent_path = os.path.join(agents_catalog_path, category, agent_name)
    
    print(f"Agent path: {agent_path}")
    print(f"Agent path exists: {os.path.exists(agent_path)}")
    
    cdk_path = os.path.join(agent_path, "cdk")
    app_py_path = os.path.join(cdk_path, "app.py")
    
    print(f"CDK path: {cdk_path}")
    print(f"CDK path exists: {os.path.exists(cdk_path)}")
    print(f"App.py path: {app_py_path}")
    print(f"App.py exists: {os.path.exists(app_py_path)}")
    
    if os.path.exists(app_py_path):
        print("\nTesting stack class extraction...")
        stack_class = registry._extract_stack_class_name(app_py_path, agent_name)
        print(f"Extracted stack class: {stack_class}")
        
        if stack_class:
            print("\nTesting CDK config creation...")
            cdk_config = registry._detect_cdk_stack(agent_name, agent_path, category)
            print(f"CDK config: {cdk_config}")
        else:
            print("❌ Stack class extraction failed")
            
            # Let's manually check the app.py content
            print("\nManual app.py analysis:")
            with open(app_py_path, 'r') as f:
                content = f.read()
            
            import re
            
            # Look for class definitions
            class_pattern = r'class\s+(\w+)\s*\([^)]*\):'
            classes = re.findall(class_pattern, content)
            print(f"All classes found: {classes}")
            
            # Look for Stack classes specifically
            stack_pattern = r'class\s+(\w+)\s*\([^)]*Stack[^)]*\):'
            stack_classes = re.findall(stack_pattern, content)
            print(f"Stack classes found: {stack_classes}")
            
            # Look for imports
            import_pattern = r'from\s+\w+\s+import\s+(\w+)'
            imports = re.findall(import_pattern, content)
            print(f"Imports found: {imports}")
            
            # Check if VistaServiceStack is mentioned
            if 'VistaServiceStack' in content:
                print("✅ VistaServiceStack found in content")
            else:
                print("❌ VistaServiceStack not found in content")
    else:
        print("❌ app.py file not found")
    
except Exception as e:
    print(f"❌ Debug test failed: {e}")
    import traceback
    traceback.print_exc()