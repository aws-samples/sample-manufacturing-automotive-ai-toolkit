#!/usr/bin/env python3
"""
Test script to verify CDK project structure
"""

import sys
import os

# Add the cdk directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test that all modules can be imported correctly"""
    try:
        print("Testing imports...")
        
        # Test main stack import
        from stacks.main_stack import MainStack
        print("✅ MainStack import successful")
        
        # Test construct imports
        from stacks.constructs.storage import StorageConstruct
        from stacks.constructs.iam import IAMConstruct
        from stacks.constructs.compute import ComputeConstruct
        from stacks.constructs.codebuild import CodeBuildConstruct
        from stacks.constructs.bedrock import BedrockConstruct
        print("✅ All construct imports successful")
        
        # Test registry import
        from stacks.nested_stack_registry import AgentRegistry
        print("✅ AgentRegistry import successful")
        
        print("🎉 All imports successful! CDK project structure is valid.")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)