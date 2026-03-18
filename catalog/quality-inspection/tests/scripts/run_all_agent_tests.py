#!/usr/bin/env python3
"""
Master test script to run all individual agent tests
"""

import subprocess
import sys
import os

def run_test_script(script_name):
    """Run a test script and return success status"""
    try:
        print(f"\n{'='*60}")
        print(f"🧪 Running {script_name}")
        print(f"{'='*60}")
        
        # Get the directory of this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, script_name)
        
        # Run the test script
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=False, 
                              text=True)
        
        if result.returncode == 0:
            print(f"✅ {script_name} completed successfully")
            return True
        else:
            print(f"❌ {script_name} failed with return code {result.returncode}")
            return False
            
    except Exception as e:
        print(f"❌ Error running {script_name}: {e}")
        return False

def main():
    """Run all agent tests"""
    print("🚀 Quality Inspection Agent Test Suite")
    print("=" * 60)
    print("Testing all 6 AgentCore agents individually...")
    
    # List of test scripts to run
    test_scripts = [
        "quality_inspection_orchestrator_test.py",
        "quality_inspection_vision_agent_test.py", 
        "quality_inspection_analysis_agent_test.py",
        "quality_inspection_sop_agent_test.py",
        "quality_inspection_action_agent_test.py",
        "quality_inspection_communication_agent_test.py"
    ]
    
    # Track results
    results = {}
    
    # Run each test
    for script in test_scripts:
        agent_name = script.replace("quality_inspection_", "").replace("_test.py", "").replace("_agent", "")
        results[agent_name] = run_test_script(script)
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = 0
    failed = 0
    
    for agent, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{agent.upper():20} {status}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📈 Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All agent tests passed!")
        return 0
    else:
        print(f"⚠️  {failed} agent test(s) failed")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)