#!/usr/bin/env python3
"""
Debug test for nested stack discovery
"""

import sys
import os

# Add the cdk directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Starting debug test...")

try:
    print("1. Testing basic imports...")
    import aws_cdk as cdk
    from constructs import Construct
    print("✅ CDK imports successful")
    
    print("2. Testing our module imports...")
    from stacks.nested_stack_registry import AgentRegistry, CDKStackConfig, AgentCoreConfig
    from stacks.main_stack import MainStack
    print("✅ Our module imports successful")
    
    print("3. Testing agent discovery without CDK stack creation...")
    # Create a minimal registry without a full stack
    class MockStack:
        def __init__(self):
            self.stack_name = "TestStack"
            self.region = "us-east-1"
            self.account = "123456789012"
    
    mock_stack = MockStack()
    registry = AgentRegistry(mock_stack)
    
    print("4. Running agent discovery...")
    cdk_stacks, agentcore_agents = registry.discover_agents()
    
    print(f"✅ Discovery successful:")
    print(f"   CDK stacks: {len(cdk_stacks)}")
    print(f"   AgentCore agents: {len(agentcore_agents)}")
    
    for cdk_config in cdk_stacks:
        print(f"   - CDK: {cdk_config.name} ({cdk_config.category}) -> {cdk_config.stack_class}")
    
    for agentcore_config in agentcore_agents:
        print(f"   - AgentCore: {agentcore_config.name} ({agentcore_config.category})")
    
    print("5. Testing Vista agents discovery specifically...")
    vista_config = None
    for config in cdk_stacks:
        if config.name == '00-vista-agents':
            vista_config = config
            break
    
    if vista_config:
        print(f"✅ Vista agents found: {vista_config}")
        print(f"   Path: {vista_config.path}")
        print(f"   Stack class: {vista_config.stack_class}")
        print(f"   App.py exists: {os.path.exists(vista_config.app_py_path)}")
    else:
        print("❌ Vista agents not found")
    
    print("6. Testing Products agent discovery specifically...")
    products_config = None
    for config in agentcore_agents:
        if config.name == '00-products-agent':
            products_config = config
            break
    
    if products_config:
        print(f"✅ Products agent found: {products_config}")
        print(f"   Path: {products_config.path}")
        print(f"   Environment vars: {len(products_config.environment)}")
    else:
        print("❌ Products agent not found")
    
    print("\n🎉 Debug test completed successfully!")
    
except Exception as e:
    print(f"❌ Debug test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)