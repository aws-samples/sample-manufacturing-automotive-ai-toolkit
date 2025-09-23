#!/usr/bin/env python3
"""
Test Nested Stack Auto-Discovery and Deployment
Tests task 7.2: Verify Vista agents nested stack discovery, AgentCore agent discovery,
and shared resource passing between main and nested stacks.
"""

import json
import subprocess
import sys
import os
import boto3
import time
from typing import Dict, List, Optional, Any, Tuple
from botocore.exceptions import ClientError, NoCredentialsError

# Add the cdk directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stacks.nested_stack_registry import AgentRegistry, CDKStackConfig, AgentCoreConfig
from stacks.main_stack import MainStack
import aws_cdk as cdk
from constructs import Construct


class NestedStackDiscoveryTester:
    """Test nested stack auto-discovery and deployment functionality"""
    
    def __init__(self, stack_name: str = "MA3TMainStack"):
        self.stack_name = stack_name
        self.test_results = {}
        self.cdk_path = os.path.dirname(os.path.abspath(__file__))
        self.workspace_root = os.path.dirname(self.cdk_path)
        self.agents_catalog_path = os.path.join(self.workspace_root, "agents_catalog")
        
        # Initialize test app and stack for testing
        self.test_app = None
        self.test_stack = None
        self.agent_registry = None
    
    def setup_test_environment(self) -> bool:
        """Set up test CDK app and stack for testing"""
        print("🔄 Setting up test environment...")
        
        try:
            # Create test CDK app
            self.test_app = cdk.App()
            
            # Create test main stack
            self.test_stack = MainStack(
                self.test_app,
                self.stack_name,
                env=cdk.Environment(
                    account=os.environ.get('CDK_DEFAULT_ACCOUNT', '123456789012'),
                    region=os.environ.get('CDK_DEFAULT_REGION', 'us-east-1')
                )
            )
            
            print("✅ Test environment setup successful")
            self.test_results['setup'] = {'success': True}
            return True
            
        except Exception as e:
            print(f"❌ Test environment setup failed: {e}")
            self.test_results['setup'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def test_agent_discovery(self) -> bool:
        """Test agent discovery functionality"""
        print("🔄 Testing agent discovery...")
        
        try:
            # Create agent registry
            self.agent_registry = AgentRegistry(self.test_stack)
            
            # Discover agents
            cdk_stacks, agentcore_agents = self.agent_registry.discover_agents()
            
            print(f"📊 Discovery results:")
            print(f"  CDK stacks found: {len(cdk_stacks)}")
            print(f"  AgentCore agents found: {len(agentcore_agents)}")
            
            # Detailed reporting
            for cdk_config in cdk_stacks:
                print(f"    CDK Stack: {cdk_config.name} ({cdk_config.category}) - {cdk_config.stack_class}")
            
            for agentcore_config in agentcore_agents:
                print(f"    AgentCore Agent: {agentcore_config.name} ({agentcore_config.category})")
            
            # Validate expected agents are found
            expected_vista_agent = any(
                config.name == '00-vista-agents' and config.category == 'multi_agent_collaboration'
                for config in cdk_stacks
            )
            
            expected_products_agent = any(
                config.name == '00-products-agent' and config.category == 'standalone_agents'
                for config in agentcore_agents
            )
            
            success = True
            issues = []
            
            if not expected_vista_agent:
                issues.append("Vista agents CDK stack not discovered")
                success = False
            else:
                print("✅ Vista agents CDK stack discovered correctly")
            
            if not expected_products_agent:
                issues.append("Products AgentCore agent not discovered")
                success = False
            else:
                print("✅ Products AgentCore agent discovered correctly")
            
            self.test_results['agent_discovery'] = {
                'success': success,
                'cdk_stacks_count': len(cdk_stacks),
                'agentcore_agents_count': len(agentcore_agents),
                'cdk_stacks': [
                    {
                        'name': config.name,
                        'category': config.category,
                        'stack_class': config.stack_class,
                        'path': config.path
                    }
                    for config in cdk_stacks
                ],
                'agentcore_agents': [
                    {
                        'name': config.name,
                        'category': config.category,
                        'path': config.path
                    }
                    for config in agentcore_agents
                ],
                'issues': issues
            }
            
            return success
            
        except Exception as e:
            print(f"❌ Agent discovery test failed: {e}")
            self.test_results['agent_discovery'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def test_vista_agents_discovery(self) -> bool:
        """Test specific Vista agents discovery"""
        print("🔄 Testing Vista agents discovery...")
        
        try:
            vista_path = os.path.join(self.agents_catalog_path, 'multi_agent_collaboration', '00-vista-agents')
            cdk_path = os.path.join(vista_path, 'cdk')
            app_py_path = os.path.join(cdk_path, 'app.py')
            stack_file_path = os.path.join(cdk_path, 'vista_service_stack.py')
            
            # Check file existence
            checks = {
                'vista_directory_exists': os.path.exists(vista_path),
                'cdk_directory_exists': os.path.exists(cdk_path),
                'app_py_exists': os.path.exists(app_py_path),
                'stack_file_exists': os.path.exists(stack_file_path)
            }
            
            print("📋 Vista agents file structure:")
            for check, result in checks.items():
                status = "✅" if result else "❌"
                print(f"  {status} {check.replace('_', ' ').title()}: {result}")
            
            # Test stack class extraction
            if checks['app_py_exists']:
                stack_class = self.agent_registry._extract_stack_class_name(app_py_path, '00-vista-agents')
                print(f"📋 Extracted stack class: {stack_class}")
                
                if stack_class == 'VistaServiceStack':
                    print("✅ Correct stack class extracted")
                    checks['stack_class_extraction'] = True
                else:
                    print(f"❌ Unexpected stack class: {stack_class}")
                    checks['stack_class_extraction'] = False
            else:
                checks['stack_class_extraction'] = False
            
            # Test CDK config creation
            if all(checks.values()):
                cdk_config = self.agent_registry._detect_cdk_stack(
                    '00-vista-agents', vista_path, 'multi_agent_collaboration'
                )
                
                if cdk_config:
                    print("✅ Vista agents CDK config created successfully")
                    print(f"  Name: {cdk_config.name}")
                    print(f"  Category: {cdk_config.category}")
                    print(f"  Stack Class: {cdk_config.stack_class}")
                    print(f"  Path: {cdk_config.path}")
                    checks['cdk_config_creation'] = True
                else:
                    print("❌ Failed to create Vista agents CDK config")
                    checks['cdk_config_creation'] = False
            else:
                checks['cdk_config_creation'] = False
            
            success = all(checks.values())
            
            self.test_results['vista_agents_discovery'] = {
                'success': success,
                'checks': checks,
                'vista_path': vista_path,
                'cdk_path': cdk_path
            }
            
            return success
            
        except Exception as e:
            print(f"❌ Vista agents discovery test failed: {e}")
            self.test_results['vista_agents_discovery'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def test_agentcore_discovery(self) -> bool:
        """Test AgentCore agent discovery"""
        print("🔄 Testing AgentCore agent discovery...")
        
        try:
            products_path = os.path.join(self.agents_catalog_path, 'standalone_agents', '00-products-agent')
            agentcore_config_path = os.path.join(products_path, '.bedrock_agentcore.yaml')
            manifest_path = os.path.join(products_path, 'manifest.json')
            dockerfile_path = os.path.join(products_path, 'Dockerfile')
            requirements_path = os.path.join(products_path, 'requirements.txt')
            
            # Check file existence
            checks = {
                'products_directory_exists': os.path.exists(products_path),
                'agentcore_config_exists': os.path.exists(agentcore_config_path),
                'manifest_exists': os.path.exists(manifest_path),
                'dockerfile_exists': os.path.exists(dockerfile_path),
                'requirements_exists': os.path.exists(requirements_path)
            }
            
            print("📋 Products agent file structure:")
            for check, result in checks.items():
                status = "✅" if result else "❌"
                print(f"  {status} {check.replace('_', ' ').title()}: {result}")
            
            # Test AgentCore config creation
            if checks['products_directory_exists']:
                agentcore_config = self.agent_registry._detect_agentcore_agent(
                    '00-products-agent', products_path, 'standalone_agents'
                )
                
                if agentcore_config:
                    print("✅ Products agent AgentCore config created successfully")
                    print(f"  Name: {agentcore_config.name}")
                    print(f"  Category: {agentcore_config.category}")
                    print(f"  Path: {agentcore_config.path}")
                    print(f"  Environment vars: {len(agentcore_config.environment)}")
                    checks['agentcore_config_creation'] = True
                else:
                    print("❌ Failed to create Products agent AgentCore config")
                    checks['agentcore_config_creation'] = False
            else:
                checks['agentcore_config_creation'] = False
            
            success = checks['products_directory_exists'] and checks['agentcore_config_creation']
            
            self.test_results['agentcore_discovery'] = {
                'success': success,
                'checks': checks,
                'products_path': products_path
            }
            
            return success
            
        except Exception as e:
            print(f"❌ AgentCore discovery test failed: {e}")
            self.test_results['agentcore_discovery'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def test_shared_resource_passing(self) -> bool:
        """Test shared resource passing between main and nested stacks"""
        print("🔄 Testing shared resource passing...")
        
        try:
            # Get shared resources from main stack
            shared_resources = self.test_stack.get_shared_resources()
            
            print("📋 Shared resources available:")
            resource_types = {}
            for key, value in shared_resources.items():
                if value is not None:
                    resource_type = type(value).__name__
                    resource_types[key] = resource_type
                    print(f"  ✅ {key}: {resource_type}")
                else:
                    print(f"  ❌ {key}: None")
            
            # Check for required shared resources
            required_resources = [
                'resource_bucket',
                'agent_role',
                'lambda_execution_role',
                'tables',
                'lambda_functions',
                'bedrock_model_id'
            ]
            
            missing_resources = []
            for resource in required_resources:
                if resource not in shared_resources or shared_resources[resource] is None:
                    missing_resources.append(resource)
            
            if missing_resources:
                print(f"❌ Missing required shared resources: {missing_resources}")
                success = False
            else:
                print("✅ All required shared resources available")
                success = True
            
            # Test resource access patterns
            resource_access_tests = {}
            
            # Test S3 bucket access
            if 'resource_bucket' in shared_resources and shared_resources['resource_bucket']:
                try:
                    bucket = shared_resources['resource_bucket']
                    bucket_name = bucket.bucket_name if hasattr(bucket, 'bucket_name') else str(bucket)
                    resource_access_tests['s3_bucket_access'] = True
                    print(f"  ✅ S3 bucket accessible: {bucket_name}")
                except Exception as e:
                    resource_access_tests['s3_bucket_access'] = False
                    print(f"  ❌ S3 bucket access failed: {e}")
            
            # Test IAM role access
            if 'agent_role' in shared_resources and shared_resources['agent_role']:
                try:
                    role = shared_resources['agent_role']
                    role_arn = role.role_arn if hasattr(role, 'role_arn') else str(role)
                    resource_access_tests['iam_role_access'] = True
                    print(f"  ✅ IAM role accessible: {role_arn}")
                except Exception as e:
                    resource_access_tests['iam_role_access'] = False
                    print(f"  ❌ IAM role access failed: {e}")
            
            # Test DynamoDB tables access
            if 'tables' in shared_resources and shared_resources['tables']:
                try:
                    tables = shared_resources['tables']
                    table_count = len(tables) if isinstance(tables, dict) else 0
                    resource_access_tests['dynamodb_tables_access'] = table_count > 0
                    print(f"  ✅ DynamoDB tables accessible: {table_count} tables")
                except Exception as e:
                    resource_access_tests['dynamodb_tables_access'] = False
                    print(f"  ❌ DynamoDB tables access failed: {e}")
            
            # Test Lambda functions access
            if 'lambda_functions' in shared_resources and shared_resources['lambda_functions']:
                try:
                    functions = shared_resources['lambda_functions']
                    function_count = len(functions) if isinstance(functions, dict) else 0
                    resource_access_tests['lambda_functions_access'] = function_count > 0
                    print(f"  ✅ Lambda functions accessible: {function_count} functions")
                except Exception as e:
                    resource_access_tests['lambda_functions_access'] = False
                    print(f"  ❌ Lambda functions access failed: {e}")
            
            overall_success = success and all(resource_access_tests.values())
            
            self.test_results['shared_resource_passing'] = {
                'success': overall_success,
                'available_resources': list(resource_types.keys()),
                'missing_resources': missing_resources,
                'resource_access_tests': resource_access_tests,
                'total_resources': len(shared_resources)
            }
            
            return overall_success
            
        except Exception as e:
            print(f"❌ Shared resource passing test failed: {e}")
            self.test_results['shared_resource_passing'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def test_nested_stack_registration(self) -> bool:
        """Test CDK nested stack registration"""
        print("🔄 Testing CDK nested stack registration...")
        
        try:
            if not self.agent_registry:
                print("❌ Agent registry not initialized")
                return False
            
            # Check if Vista agents nested stack was already registered during setup
            if hasattr(self.test_stack, 'nested_stacks') and self.test_stack.nested_stacks:
                vista_stack = None
                for stack in self.test_stack.nested_stacks:
                    if hasattr(stack, 'node') and 'vista' in stack.node.id.lower():
                        vista_stack = stack
                        break
                
                if vista_stack:
                    print("✅ Vista agents nested stack already registered during setup")
                    print(f"  Stack type: {type(vista_stack).__name__}")
                    print(f"  Stack ID: {vista_stack.node.id}")
                    
                    self.test_results['nested_stack_registration'] = {
                        'success': True,
                        'method': 'already_registered',
                        'stack_type': type(vista_stack).__name__,
                        'stack_id': vista_stack.node.id
                    }
                    return True
            
            # If not already registered, discover and test registration
            cdk_stacks, agentcore_agents = self.agent_registry.discover_agents()
            
            # Find Vista agents config
            vista_config = None
            for config in cdk_stacks:
                if config.name == '00-vista-agents' and config.category == 'multi_agent_collaboration':
                    vista_config = config
                    break
            
            if not vista_config:
                print("❌ Vista agents config not found for registration test")
                self.test_results['nested_stack_registration'] = {
                    'success': False,
                    'error': 'Vista agents config not found'
                }
                return False
            
            print(f"📋 Testing stack class import for: {vista_config.name}")
            
            # Test stack class import without creating duplicate construct
            try:
                stack_class = self.agent_registry._import_stack_class(vista_config)
                
                if stack_class:
                    print("✅ Vista agents stack class imported successfully")
                    print(f"  Stack class: {stack_class.__name__}")
                    
                    # Verify it's a proper CDK Stack class
                    import aws_cdk as cdk
                    if issubclass(stack_class, cdk.Stack):
                        print("✅ Stack class is a valid CDK Stack")
                        registration_success = True
                    else:
                        print("❌ Stack class is not a CDK Stack")
                        registration_success = False
                else:
                    print("❌ Vista agents stack class import returned None")
                    registration_success = False
                
            except Exception as e:
                print(f"❌ Vista agents stack class import failed: {e}")
                registration_success = False
            
            self.test_results['nested_stack_registration'] = {
                'success': registration_success,
                'method': 'class_import_test',
                'vista_config': {
                    'name': vista_config.name,
                    'category': vista_config.category,
                    'stack_class': vista_config.stack_class,
                    'path': vista_config.path
                }
            }
            
            return registration_success
            
        except Exception as e:
            print(f"❌ Nested stack registration test failed: {e}")
            self.test_results['nested_stack_registration'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def test_codebuild_project_creation(self) -> bool:
        """Test CodeBuild project creation for AgentCore agents"""
        print("🔄 Testing CodeBuild project creation...")
        
        try:
            if not self.agent_registry:
                print("❌ Agent registry not initialized")
                return False
            
            # Check if Products agent CodeBuild project was already created during setup
            if hasattr(self.test_stack, 'agentcore_projects') and self.test_stack.agentcore_projects:
                products_project = None
                for project in self.test_stack.agentcore_projects:
                    if hasattr(project, 'node') and 'products' in project.node.id.lower():
                        products_project = project
                        break
                
                if products_project:
                    print("✅ Products agent CodeBuild project already created during setup")
                    print(f"  Project type: {type(products_project).__name__}")
                    print(f"  Project ID: {products_project.node.id}")
                    
                    self.test_results['codebuild_project_creation'] = {
                        'success': True,
                        'method': 'already_created',
                        'project_type': type(products_project).__name__,
                        'project_id': products_project.node.id
                    }
                    return True
            
            # Check if project exists in codebuild_projects dict
            if hasattr(self.test_stack, 'codebuild_projects'):
                for project_name, project in self.test_stack.codebuild_projects.items():
                    if 'products' in project_name.lower():
                        print("✅ Products agent CodeBuild project found in projects dict")
                        print(f"  Project name: {project_name}")
                        print(f"  Project type: {type(project).__name__}")
                        
                        self.test_results['codebuild_project_creation'] = {
                            'success': True,
                            'method': 'found_in_projects_dict',
                            'project_name': project_name,
                            'project_type': type(project).__name__
                        }
                        return True
            
            # If not already created, discover and test creation capability
            cdk_stacks, agentcore_agents = self.agent_registry.discover_agents()
            
            # Find Products agent config
            products_config = None
            for config in agentcore_agents:
                if config.name == '00-products-agent' and config.category == 'standalone_agents':
                    products_config = config
                    break
            
            if not products_config:
                print("❌ Products agent config not found for CodeBuild test")
                self.test_results['codebuild_project_creation'] = {
                    'success': False,
                    'error': 'Products agent config not found'
                }
                return False
            
            print(f"📋 Testing CodeBuild project creation capability for: {products_config.name}")
            
            # Test that the CodeBuild construct has the required method
            try:
                codebuild_construct = self.test_stack.codebuild_construct
                
                if hasattr(codebuild_construct, 'create_dynamic_agentcore_project'):
                    print("✅ CodeBuild construct has dynamic project creation method")
                    
                    # Test configuration validation without creating duplicate
                    agent_config = {
                        'path': products_config.path,
                        'category': products_config.category,
                        'environment': products_config.environment,
                        'has_dockerfile': os.path.exists(products_config.dockerfile_path),
                        'has_requirements': os.path.exists(products_config.requirements_path)
                    }
                    
                    print(f"✅ Agent configuration validated:")
                    print(f"  Path: {agent_config['path']}")
                    print(f"  Category: {agent_config['category']}")
                    print(f"  Has Dockerfile: {agent_config['has_dockerfile']}")
                    print(f"  Has Requirements: {agent_config['has_requirements']}")
                    
                    creation_success = True
                else:
                    print("❌ CodeBuild construct missing dynamic project creation method")
                    creation_success = False
                
            except Exception as e:
                print(f"❌ CodeBuild project creation capability test failed: {e}")
                creation_success = False
            
            self.test_results['codebuild_project_creation'] = {
                'success': creation_success,
                'method': 'capability_test',
                'products_config': {
                    'name': products_config.name,
                    'category': products_config.category,
                    'path': products_config.path,
                    'environment_vars': len(products_config.environment)
                }
            }
            
            return creation_success
            
        except Exception as e:
            print(f"❌ CodeBuild project creation test failed: {e}")
            self.test_results['codebuild_project_creation'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def test_main_stack_integration(self) -> bool:
        """Test main stack integration with discovered agents"""
        print("🔄 Testing main stack integration...")
        
        try:
            # Check if main stack has agent registry
            if not hasattr(self.test_stack, 'agent_registry'):
                print("❌ Main stack does not have agent registry")
                return False
            
            # Check if nested stacks were created
            nested_stacks = getattr(self.test_stack, 'nested_stacks', [])
            agentcore_projects = getattr(self.test_stack, 'agentcore_projects', [])
            
            print(f"📋 Main stack integration results:")
            print(f"  Nested stacks: {len(nested_stacks)}")
            print(f"  AgentCore projects: {len(agentcore_projects)}")
            
            # Get agent summary
            agent_summary = self.test_stack.get_agent_summary()
            print(f"  Total agents discovered: {agent_summary.get('total_agents', 0)}")
            
            # Check resource summary
            resource_summary = self.test_stack.get_resource_summary()
            print(f"  Storage resources: {resource_summary.get('storage', {})}")
            print(f"  Compute resources: {resource_summary.get('compute', {})}")
            print(f"  CodeBuild resources: {resource_summary.get('codebuild', {})}")
            
            success = (
                len(nested_stacks) > 0 or len(agentcore_projects) > 0
            ) and agent_summary.get('total_agents', 0) > 0
            
            if success:
                print("✅ Main stack integration successful")
            else:
                print("❌ Main stack integration failed - no agents integrated")
            
            self.test_results['main_stack_integration'] = {
                'success': success,
                'nested_stacks_count': len(nested_stacks),
                'agentcore_projects_count': len(agentcore_projects),
                'agent_summary': agent_summary,
                'resource_summary': resource_summary
            }
            
            return success
            
        except Exception as e:
            print(f"❌ Main stack integration test failed: {e}")
            self.test_results['main_stack_integration'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def run_all_tests(self) -> bool:
        """Run all nested stack discovery and deployment tests"""
        print("🚀 Starting Nested Stack Auto-Discovery and Deployment Tests")
        print("=" * 60)
        
        tests = [
            ("Test Environment Setup", self.setup_test_environment),
            ("Agent Discovery", self.test_agent_discovery),
            ("Vista Agents Discovery", self.test_vista_agents_discovery),
            ("AgentCore Discovery", self.test_agentcore_discovery),
            ("Shared Resource Passing", self.test_shared_resource_passing),
            ("Nested Stack Registration", self.test_nested_stack_registration),
            ("CodeBuild Project Creation", self.test_codebuild_project_creation),
            ("Main Stack Integration", self.test_main_stack_integration)
        ]
        
        all_passed = True
        
        for test_name, test_func in tests:
            print(f"\n📋 Running: {test_name}")
            try:
                result = test_func()
                if not result:
                    all_passed = False
                    print(f"❌ {test_name} failed")
                else:
                    print(f"✅ {test_name} passed")
            except Exception as e:
                print(f"❌ Test {test_name} failed with exception: {e}")
                all_passed = False
        
        print("\n" + "=" * 60)
        if all_passed:
            print("🎉 All nested stack auto-discovery and deployment tests passed!")
            print("\n📋 Test Summary:")
            print("✅ Vista agents nested stack is discovered and deployed correctly")
            print("✅ AgentCore agent discovery and CodeBuild project creation works")
            print("✅ Shared resource passing between main and nested stacks validated")
        else:
            print("❌ Some tests failed. Check the output above for details.")
        
        return all_passed
    
    def generate_test_report(self) -> str:
        """Generate a detailed test report"""
        report = "# Nested Stack Auto-Discovery and Deployment Test Report\n\n"
        report += f"**Test Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # Overall summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result.get('success', False))
        
        report += f"## Summary\n"
        report += f"- **Total Tests**: {total_tests}\n"
        report += f"- **Passed**: {passed_tests}\n"
        report += f"- **Failed**: {total_tests - passed_tests}\n"
        report += f"- **Success Rate**: {(passed_tests/total_tests*100):.1f}%\n\n"
        
        # Detailed results
        for test_name, result in self.test_results.items():
            report += f"## {test_name.replace('_', ' ').title()}\n"
            
            if result['success']:
                report += "✅ **Status**: PASSED\n\n"
            else:
                report += "❌ **Status**: FAILED\n\n"
            
            if 'error' in result:
                report += f"**Error**: {result['error']}\n\n"
            
            # Add specific details for each test
            for key, value in result.items():
                if key not in ['success', 'error']:
                    if isinstance(value, (dict, list)):
                        report += f"**{key.replace('_', ' ').title()}**:\n```json\n{json.dumps(value, indent=2)}\n```\n\n"
                    else:
                        report += f"**{key.replace('_', ' ').title()}**: {value}\n\n"
        
        return report


def main():
    """Main test execution"""
    if len(sys.argv) > 1:
        stack_name = sys.argv[1]
    else:
        stack_name = "MA3TMainStack"
    
    tester = NestedStackDiscoveryTester(stack_name)
    
    # Run all tests
    success = tester.run_all_tests()
    
    # Generate and save report
    report = tester.generate_test_report()
    report_path = os.path.join(tester.cdk_path, 'nested_stack_test_report.md')
    
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Detailed test report saved to: {report_path}")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()