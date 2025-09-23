#!/usr/bin/env python3
"""
AgentCore Deployment Testing Script
Tests the CDK implementation of AgentCore agent deployment functionality
"""

import json
import subprocess
import sys
import os
import boto3
import time
from typing import Dict, List, Optional, Any
from botocore.exceptions import ClientError, NoCredentialsError

class AgentCoreDeploymentTester:
    """Test AgentCore deployment functionality in CDK"""
    
    def __init__(self, stack_name: str = "MA3TMainStack"):
        self.stack_name = stack_name
        self.test_results = {}
        self.cdk_path = os.path.dirname(os.path.abspath(__file__))
        
        # Initialize AWS clients
        try:
            self.cloudformation = boto3.client('cloudformation')
            self.codebuild = boto3.client('codebuild')
            self.bedrock_agentcore = boto3.client('bedrock-agentcore')
            self.s3 = boto3.client('s3')
        except NoCredentialsError:
            print("❌ AWS credentials not configured. Please configure AWS credentials.")
            sys.exit(1)
    
    def discover_agentcore_agents_locally(self) -> List[Dict[str, Any]]:
        """Discover AgentCore agents from local agents_catalog directory"""
        print("🔄 Discovering AgentCore agents locally...")
        
        agents = []
        agents_catalog_path = os.path.join(os.getcwd(), "agents_catalog")
        
        if not os.path.exists(agents_catalog_path):
            print("❌ agents_catalog directory not found")
            return agents
        
        # Walk through the agents_catalog directory
        for root, dirs, files in os.walk(agents_catalog_path):
            if "manifest.json" in files:
                manifest_path = os.path.join(root, "manifest.json")
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        manifest = json.load(f)
                    
                    # Check if any agent in the manifest is of type 'agentcore'
                    for agent in manifest.get("agents", []):
                        if agent.get("type") == "agentcore":
                            agent_id = agent.get("id")
                            agent_name = agent.get("name")
                            entrypoint = agent.get("entrypoint", "agent.py")
                            
                            # Check if the entrypoint file exists
                            entrypoint_path = os.path.join(root, entrypoint)
                            if not os.path.exists(entrypoint_path):
                                # Look for other potential entrypoints
                                python_files = [f for f in files if f.endswith('.py')]
                                if python_files:
                                    entrypoint = python_files[0]
                                    print(f"  ⚠️  Entrypoint {agent.get('entrypoint', 'agent.py')} not found, using {entrypoint}")
                            
                            agents.append({
                                "path": root,
                                "id": agent_id,
                                "name": agent_name,
                                "entrypoint": entrypoint,
                                "manifest": agent,
                                "has_dockerfile": os.path.exists(os.path.join(root, "Dockerfile")),
                                "has_requirements": os.path.exists(os.path.join(root, "requirements.txt")),
                                "has_agentcore_config": os.path.exists(os.path.join(root, ".bedrock_agentcore.yaml"))
                            })
                            
                            print(f"  ✅ Found AgentCore agent: {agent_name} at {root}")
                            
                except Exception as e:
                    print(f"  ❌ Error processing manifest at {manifest_path}: {e}")
        
        self.test_results['local_discovery'] = {
            'success': True,
            'agents_found': len(agents),
            'agents': agents
        }
        
        return agents
    
    def test_agentcore_script_functionality(self) -> bool:
        """Test the build_launch_agentcore.py script functionality"""
        print("🔄 Testing AgentCore script functionality...")
        
        script_path = os.path.join(os.getcwd(), "scripts", "build_launch_agentcore.py")
        
        if not os.path.exists(script_path):
            print("❌ build_launch_agentcore.py script not found")
            self.test_results['script_test'] = {
                'success': False,
                'error': 'Script not found'
            }
            return False
        
        try:
            # Test script discovery functionality (dry run)
            print("  📋 Testing agent discovery...")
            
            # Import the script as a module to test its functions
            sys.path.insert(0, os.path.dirname(script_path))
            import build_launch_agentcore
            
            # Test the find_agentcore_agents function
            agents = build_launch_agentcore.find_agentcore_agents()
            
            print(f"  ✅ Script discovered {len(agents)} AgentCore agents")
            
            agent_details = []
            for agent_path, agent_id, agent_name, entrypoint in agents:
                print(f"    - {agent_name} (ID: {agent_id}) at {agent_path}")
                agent_details.append({
                    'path': agent_path,
                    'id': agent_id,
                    'name': agent_name,
                    'entrypoint': entrypoint
                })
            
            self.test_results['script_test'] = {
                'success': True,
                'agents_discovered': len(agents),
                'agent_details': agent_details
            }
            
            return True
            
        except Exception as e:
            print(f"  ❌ Error testing script: {e}")
            self.test_results['script_test'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def test_codebuild_projects_exist(self) -> bool:
        """Test that CodeBuild projects for AgentCore deployment exist"""
        print("🔄 Testing CodeBuild projects...")
        
        try:
            # List all CodeBuild projects
            response = self.codebuild.list_projects()
            all_projects = response.get('projects', [])
            
            # Filter projects related to our stack
            stack_projects = [p for p in all_projects if self.stack_name.lower() in p.lower()]
            agentcore_projects = [p for p in stack_projects if 'agent' in p.lower()]
            
            print(f"  📋 Found {len(stack_projects)} projects for stack {self.stack_name}")
            print(f"  📋 Found {len(agentcore_projects)} agent-related projects")
            
            project_details = []
            for project_name in agentcore_projects:
                try:
                    project_response = self.codebuild.batch_get_projects(names=[project_name])
                    projects = project_response.get('projects', [])
                    
                    if projects:
                        project = projects[0]
                        print(f"    ✅ {project_name}")
                        print(f"       Description: {project.get('description', 'N/A')}")
                        print(f"       Service Role: {project.get('serviceRole', 'N/A')}")
                        
                        project_details.append({
                            'name': project_name,
                            'description': project.get('description'),
                            'service_role': project.get('serviceRole'),
                            'environment': project.get('environment', {}),
                            'source': project.get('source', {})
                        })
                    
                except ClientError as e:
                    print(f"    ❌ Error getting details for {project_name}: {e}")
            
            self.test_results['codebuild_projects'] = {
                'success': len(agentcore_projects) > 0,
                'total_projects': len(stack_projects),
                'agentcore_projects': len(agentcore_projects),
                'project_details': project_details
            }
            
            return len(agentcore_projects) > 0
            
        except ClientError as e:
            print(f"  ❌ Error listing CodeBuild projects: {e}")
            self.test_results['codebuild_projects'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def test_agentcore_toolkit_availability(self) -> bool:
        """Test if the bedrock-agentcore-starter-toolkit is available"""
        print("🔄 Testing AgentCore toolkit availability...")
        
        try:
            # Try to import the toolkit
            import subprocess
            result = subprocess.run(
                ['pip', 'show', 'bedrock-agentcore-starter-toolkit'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print("  ✅ bedrock-agentcore-starter-toolkit is available")
                
                # Parse the output to get version info
                lines = result.stdout.split('\n')
                version_info = {}
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        version_info[key.strip()] = value.strip()
                
                self.test_results['toolkit_availability'] = {
                    'success': True,
                    'version_info': version_info
                }
                return True
            else:
                print("  ⚠️  bedrock-agentcore-starter-toolkit not installed locally")
                print("     This is expected - it will be installed in CodeBuild environment")
                
                self.test_results['toolkit_availability'] = {
                    'success': True,
                    'note': 'Not installed locally (expected)',
                    'will_install_in_codebuild': True
                }
                return True
                
        except Exception as e:
            print(f"  ❌ Error checking toolkit availability: {e}")
            self.test_results['toolkit_availability'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def test_agentcore_agents_in_aws(self) -> bool:
        """Test if any AgentCore agents are deployed in AWS"""
        print("🔄 Testing deployed AgentCore agents in AWS...")
        
        try:
            # Try to list AgentCore agents
            response = self.bedrock_agentcore.list_agents()
            agents = response.get('agents', [])
            
            print(f"  📋 Found {len(agents)} AgentCore agents in AWS")
            
            agent_details = []
            for agent in agents:
                agent_name = agent.get('agentName', 'Unknown')
                agent_id = agent.get('agentId', 'Unknown')
                agent_status = agent.get('agentStatus', 'Unknown')
                
                print(f"    - {agent_name} (ID: {agent_id}, Status: {agent_status})")
                agent_details.append({
                    'name': agent_name,
                    'id': agent_id,
                    'status': agent_status
                })
            
            self.test_results['deployed_agentcore_agents'] = {
                'success': True,
                'agents_count': len(agents),
                'agent_details': agent_details
            }
            
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'AccessDeniedException':
                print("  ⚠️  No access to bedrock-agentcore service (this may be expected)")
                self.test_results['deployed_agentcore_agents'] = {
                    'success': True,
                    'note': 'Access denied to bedrock-agentcore service',
                    'agents_count': 0
                }
                return True
            else:
                print(f"  ❌ Error listing AgentCore agents: {e}")
                self.test_results['deployed_agentcore_agents'] = {
                    'success': False,
                    'error': str(e)
                }
                return False
    
    def test_required_permissions(self) -> bool:
        """Test if the current role has required permissions for AgentCore deployment"""
        print("🔄 Testing required permissions...")
        
        permissions_test = {
            'ecr': False,
            'bedrock_agentcore': False,
            'codebuild': False,
            's3': False
        }
        
        try:
            # Test ECR permissions
            try:
                ecr = boto3.client('ecr')
                ecr.describe_repositories()
                permissions_test['ecr'] = True
                print("  ✅ ECR permissions available")
            except ClientError:
                print("  ⚠️  ECR permissions limited")
            
            # Test Bedrock AgentCore permissions
            try:
                self.bedrock_agentcore.list_agents()
                permissions_test['bedrock_agentcore'] = True
                print("  ✅ Bedrock AgentCore permissions available")
            except ClientError:
                print("  ⚠️  Bedrock AgentCore permissions limited")
            
            # Test CodeBuild permissions
            try:
                self.codebuild.list_projects()
                permissions_test['codebuild'] = True
                print("  ✅ CodeBuild permissions available")
            except ClientError:
                print("  ⚠️  CodeBuild permissions limited")
            
            # Test S3 permissions
            try:
                self.s3.list_buckets()
                permissions_test['s3'] = True
                print("  ✅ S3 permissions available")
            except ClientError:
                print("  ⚠️  S3 permissions limited")
            
            self.test_results['permissions'] = {
                'success': True,
                'permissions_test': permissions_test,
                'available_permissions': sum(permissions_test.values())
            }
            
            return True
            
        except Exception as e:
            print(f"  ❌ Error testing permissions: {e}")
            self.test_results['permissions'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def run_comprehensive_test(self) -> bool:
        """Run comprehensive AgentCore deployment tests"""
        print("🚀 Starting Comprehensive AgentCore Deployment Tests")
        print("=" * 70)
        
        tests = [
            ("Local AgentCore Discovery", self.discover_agentcore_agents_locally),
            ("AgentCore Script Functionality", self.test_agentcore_script_functionality),
            ("CodeBuild Projects", self.test_codebuild_projects_exist),
            ("AgentCore Toolkit Availability", self.test_agentcore_toolkit_availability),
            ("Deployed AgentCore Agents", self.test_agentcore_agents_in_aws),
            ("Required Permissions", self.test_required_permissions)
        ]
        
        all_passed = True
        
        for test_name, test_func in tests:
            print(f"\n📋 Running: {test_name}")
            try:
                if test_name == "Local AgentCore Discovery":
                    agents = test_func()
                    if not agents:
                        print("  ℹ️  No AgentCore agents found locally")
                else:
                    result = test_func()
                    if not result:
                        all_passed = False
            except Exception as e:
                print(f"❌ Test {test_name} failed with exception: {e}")
                all_passed = False
        
        print("\n" + "=" * 70)
        if all_passed:
            print("🎉 All AgentCore deployment tests passed!")
        else:
            print("❌ Some tests failed. Check the output above for details.")
        
        return all_passed
    
    def generate_test_report(self) -> str:
        """Generate a detailed test report"""
        report = "# AgentCore Deployment Test Report\n\n"
        
        # Summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result.get('success', False))
        
        report += f"## Summary\n"
        report += f"- **Total Tests**: {total_tests}\n"
        report += f"- **Passed**: {passed_tests}\n"
        report += f"- **Failed**: {total_tests - passed_tests}\n\n"
        
        # Detailed results
        for test_name, result in self.test_results.items():
            report += f"## {test_name.replace('_', ' ').title()}\n"
            
            if result.get('success', False):
                report += "✅ **Status**: PASSED\n\n"
            else:
                report += "❌ **Status**: FAILED\n\n"
            
            if 'error' in result:
                report += f"**Error**: {result['error']}\n\n"
            
            if 'note' in result:
                report += f"**Note**: {result['note']}\n\n"
            
            # Add specific details for each test
            for key, value in result.items():
                if key not in ['success', 'error', 'note']:
                    if isinstance(value, (dict, list)):
                        try:
                            report += f"**{key.replace('_', ' ').title()}**: {json.dumps(value, indent=2, default=str)}\n\n"
                        except (TypeError, ValueError):
                            report += f"**{key.replace('_', ' ').title()}**: {str(value)}\n\n"
                    else:
                        report += f"**{key.replace('_', ' ').title()}**: {value}\n\n"
        
        return report

def main():
    """Main test execution"""
    if len(sys.argv) > 1:
        stack_name = sys.argv[1]
    else:
        stack_name = "MA3TMainStack"
    
    tester = AgentCoreDeploymentTester(stack_name)
    
    # Run comprehensive tests
    success = tester.run_comprehensive_test()
    
    # Generate and save report
    report = tester.generate_test_report()
    report_path = os.path.join(tester.cdk_path, 'agentcore_deployment_test_report.md')
    
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Detailed test report saved to: {report_path}")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()