#!/usr/bin/env python3
"""
CDK-Nag Security and Compliance Scanner for MA3T
Runs security and compliance checks on all CDK stacks
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def run_cdk_nag():
    """Run cdk-nag checks on the MA3T CDK stacks"""
    
    # Change to CDK directory
    cdk_dir = Path(__file__).parent.parent / "cdk"
    os.chdir(cdk_dir)
    
    print("🔍 Running CDK-Nag security and compliance checks...")
    print(f"📁 Working directory: {cdk_dir}")
    
    try:
        # Install dependencies
        print("\n📦 Installing CDK dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True, capture_output=True)
        
        # Run CDK synth with nag checks
        print("\n🔍 Running CDK synth with nag checks...")
        result = subprocess.run(
            ["cdk", "synth", "--all"],
            capture_output=True,
            text=True
        )
        
        print("📊 CDK-Nag Results:")
        print("=" * 50)
        
        if result.returncode == 0:
            print("✅ CDK synthesis completed successfully!")
            if result.stdout:
                print("\nOutput:")
                print(result.stdout)
        else:
            print("❌ CDK synthesis failed or found issues:")
            if result.stderr:
                print("\nErrors/Warnings:")
                print(result.stderr)
            
        # Parse and summarize nag findings
        if "cdk.out" in os.listdir("."):
            print("\n📋 Analyzing CDK-Nag findings...")
            analyze_nag_results()
            
        return result.returncode == 0
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running CDK commands: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def analyze_nag_results():
    """Analyze CDK-Nag results from cdk.out directory"""
    
    cdk_out_dir = Path("cdk.out")
    if not cdk_out_dir.exists():
        print("⚠️  No cdk.out directory found")
        return
    
    # Look for nag report files
    nag_files = list(cdk_out_dir.glob("**/NagReport*.json"))
    
    if not nag_files:
        print("ℹ️  No specific nag report files found, but checks were applied during synth")
        return
    
    total_violations = 0
    total_suppressions = 0
    
    for nag_file in nag_files:
        try:
            with open(nag_file, 'r') as f:
                nag_data = json.load(f)
                
            violations = nag_data.get('violations', [])
            suppressions = nag_data.get('suppressions', [])
            
            total_violations += len(violations)
            total_suppressions += len(suppressions)
            
            print(f"\n📄 {nag_file.name}:")
            print(f"   🚨 Violations: {len(violations)}")
            print(f"   🔇 Suppressions: {len(suppressions)}")
            
            # Show top violations
            if violations:
                print("   Top violations:")
                for i, violation in enumerate(violations[:3]):
                    rule_id = violation.get('ruleId', 'Unknown')
                    resource = violation.get('resource', 'Unknown')
                    print(f"     {i+1}. {rule_id} - {resource}")
                    
        except Exception as e:
            print(f"⚠️  Error reading {nag_file}: {e}")
    
    print(f"\n📊 Summary:")
    print(f"   Total violations: {total_violations}")
    print(f"   Total suppressions: {total_suppressions}")
    
    if total_violations > 0:
        print(f"\n💡 To suppress specific violations, add NagSuppressions to your stacks")
        print(f"   Example: NagSuppressions.add_stack_suppressions(stack, [{{\"id\": \"RuleId\", \"reason\": \"Justification\"}}])")

def main():
    """Main entry point"""
    print("🛡️  MA3T CDK-Nag Security Scanner")
    print("=" * 40)
    
    success = run_cdk_nag()
    
    if success:
        print("\n✅ CDK-Nag scan completed successfully!")
        print("💡 Review any violations above and consider adding suppressions if justified")
    else:
        print("\n❌ CDK-Nag scan encountered issues")
        print("🔧 Check your CDK configuration and try again")
        sys.exit(1)

if __name__ == "__main__":
    main()
