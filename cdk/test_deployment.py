#!/usr/bin/env python3
"""
CDK Stack Deployment Testing Script
Tests CDK stack synthesis, deployment validation, and resource verification
"""

import json
import subprocess
import sys
import os
import boto3
import time
from typing import Dict, List, Optional, Any
from botocore.exceptions import ClientError, NoCredentialsError

class CDKDeploymentTester:
    """Test CDK stack deployment and functionality"""
    
    def __init__(self, stack_name: str = "MA3TMainStack"):
        self.stack_name = stack_name
        self.test_results = {}
        self.cdk_path = os.path.dirname(os.path.abspath(__file__))
        
        # Initialize AWS clients
        try:
            self.cloudformation = boto3.client('cloudformation')
            self.s3 = boto3.client('s3')
            self.dynamodb = boto3.client('dynamodb')
            self.lambda_client = boto3.client('lambda')
            self.bedrock_agent = boto3.client('bedrock-agent')
            self.codebuild = boto3.client('codebuild')
            self.iam = boto3.client('iam')
        except NoCredentialsError:
            print("❌ AWS credentials not configured. Please configure AWS credentials.")
            sys.exit(1)
    
    def run_command(self, command: List[str], cwd: Optional[str] = None) -> Dict[str, Any]:
        """Run a shell command and return result"""
        try:
            result = subprocess.run(
                command,
                cwd=cwd or self.cdk_path,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'stdout': '',
                'stderr': 'Command timed out after 5 minutes',
                'returncode': -1
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def test_cdk_synthesis(self) -> bool:
        """Test CDK stack synthesis"""
        print("🔄 Testing CDK stack synthesis...")
        
        # First, install dependencies
        print("  📦 Installing CDK dependencies...")
        install_result = self.run_command(['pip', 'install', '-r', 'requirements.txt'])
        if not install_result['success']:
            print(f"❌ Failed to install dependencies: {install_result['stderr']}")
            self.test_results['synthesis'] = {
                'success': False,
                'error': f"Dependency installation failed: {install_result['stderr']}"
            }
            return False
        
        # Test CDK synthesis
        synth_result = self.run_command(['cdk', 'synth'])
        
        if synth_result['success']:
            print("✅ CDK stack synthesis successful")
            
            # Check if CloudFormation template was generated
            template_path = os.path.join(self.cdk_path, 'cdk.out', f'{self.stack_name}.template.json')
            if os.path.exists(template_path):
                print("✅ CloudFormation template generated successfully")
                
                # Validate template structure
                try:
                    with open(template_path, 'r') as f:
                        template = json.load(f)
                    
                    required_sections = ['Resources', 'Parameters', 'Outputs']
                    missing_sections = [s for s in required_sections if s not in template]
                    
                    if missing_sections:
                        print(f"⚠️  Template missing sections: {missing_sections}")
                    else:
                        print("✅ Template structure validation passed")
                    
                    # Count resources
                    resource_count = len(template.get('Resources', {}))
                    print(f"📊 Template contains {resource_count} resources")
                    
                    self.test_results['synthesis'] = {
                        'success': True,
                        'template_path': template_path,
                        'resource_count': resource_count,
                        'missing_sections': missing_sections
                    }
                    return True
                    
                except json.JSONDecodeError as e:
                    print(f"❌ Invalid JSON in generated template: {e}")
                    self.test_results['synthesis'] = {
                        'success': False,
                        'error': f"Invalid template JSON: {e}"
                    }
                    return False
            else:
                print(f"❌ CloudFormation template not found at {template_path}")
                self.test_results['synthesis'] = {
                    'success': False,
                    'error': "CloudFormation template not generated"
                }
                return False
        else:
            print(f"❌ CDK synthesis failed: {synth_result['stderr']}")
            self.test_results['synthesis'] = {
                'success': False,
                'error': synth_result['stderr']
            }
            return False
    
    def test_stack_deployment_dry_run(self) -> bool:
        """Test stack deployment validation without actually deploying"""
        print("🔄 Testing CDK deployment validation...")
        
        # Use CDK diff to validate deployment without actually deploying
        diff_result = self.run_command(['cdk', 'diff'])
        
        if diff_result['success']:
            print("✅ CDK deployment validation successful")
            self.test_results['deployment_validation'] = {
                'success': True,
                'diff_output': diff_result['stdout']
            }
            return True
        else:
            print(f"❌ CDK deployment validation failed: {diff_result['stderr']}")
            self.test_results['deployment_validation'] = {
                'success': False,
                'error': diff_result['stderr']
            }
            return False
    
    def check_node_version(self) -> bool:
        """Check Node.js version compatibility"""
        print("🔄 Checking Node.js version...")
        
        try:
            result = self.run_command(['node', '--version'])
            if result['success']:
                version = result['stdout'].strip()
                print(f"📋 Node.js version: {version}")
                
                # Extract major version number
                major_version = int(version.replace('v', '').split('.')[0])
                
                # Check if version is supported (18, 20, 22, 24)
                supported_versions = [18, 20, 22, 24]
                if major_version in supported_versions:
                    print("✅ Node.js version is supported")
                    self.test_results['node_version'] = {
                        'success': True,
                        'version': version,
                        'major_version': major_version
                    }
                    return True
                else:
                    print(f"⚠️  Node.js version {major_version} may not be fully supported")
                    print(f"   Supported versions: {supported_versions}")
                    self.test_results['node_version'] = {
                        'success': False,
                        'version': version,
                        'major_version': major_version,
                        'warning': f'Version {major_version} may not be supported'
                    }
                    return False
            else:
                print("❌ Could not determine Node.js version")
                self.test_results['node_version'] = {
                    'success': False,
                    'error': 'Could not run node --version'
                }
                return False
                
        except Exception as e:
            print(f"❌ Node.js version check failed: {e}")
            self.test_results['node_version'] = {
                'success': False,
                'error': str(e)
            }
            return False

    def check_aws_environment(self) -> bool:
        """Check if AWS environment is properly configured"""
        print("🔄 Checking AWS environment...")
        
        try:
            # Check AWS credentials
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            print(f"✅ AWS credentials configured for account: {identity['Account']}")
            
            # Check required permissions by testing basic operations
            try:
                self.cloudformation.list_stacks()
                print("✅ CloudFormation permissions verified")
            except ClientError as e:
                print(f"❌ CloudFormation permissions issue: {e}")
                return False
            
            try:
                self.s3.list_buckets()
                print("✅ S3 permissions verified")
            except ClientError as e:
                print(f"❌ S3 permissions issue: {e}")
                return False
            
            self.test_results['aws_environment'] = {
                'success': True,
                'account_id': identity['Account'],
                'user_arn': identity['Arn']
            }
            return True
            
        except Exception as e:
            print(f"❌ AWS environment check failed: {e}")
            self.test_results['aws_environment'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def validate_template_resources(self) -> bool:
        """Validate that the generated template contains expected resources"""
        print("🔄 Validating template resources...")
        
        template_path = os.path.join(self.cdk_path, 'cdk.out', f'{self.stack_name}.template.json')
        
        if not os.path.exists(template_path):
            print("❌ Template file not found")
            return False
        
        try:
            with open(template_path, 'r') as f:
                template = json.load(f)
            
            resources = template.get('Resources', {})
            
            # Expected resource types
            expected_resource_types = [
                'AWS::S3::Bucket',
                'AWS::DynamoDB::Table',
                'AWS::IAM::Role',
                'AWS::Lambda::Function',
                'AWS::CodeBuild::Project'
            ]
            
            found_types = set()
            resource_details = {}
            
            for resource_id, resource in resources.items():
                resource_type = resource.get('Type')
                if resource_type:
                    found_types.add(resource_type)
                    if resource_type not in resource_details:
                        resource_details[resource_type] = []
                    resource_details[resource_type].append(resource_id)
            
            # Check for expected resources
            missing_types = set(expected_resource_types) - found_types
            
            print(f"📊 Found resource types: {sorted(found_types)}")
            
            if missing_types:
                print(f"⚠️  Missing expected resource types: {sorted(missing_types)}")
            else:
                print("✅ All expected resource types found")
            
            # Print resource counts
            for resource_type, resources_list in resource_details.items():
                print(f"  {resource_type}: {len(resources_list)} resources")
            
            self.test_results['template_validation'] = {
                'success': len(missing_types) == 0,
                'found_types': sorted(found_types),
                'missing_types': sorted(missing_types),
                'resource_details': resource_details
            }
            
            return len(missing_types) == 0
            
        except Exception as e:
            print(f"❌ Template validation failed: {e}")
            self.test_results['template_validation'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def test_cdk_bootstrap_check(self) -> bool:
        """Check if CDK bootstrap is required and available"""
        print("🔄 Checking CDK bootstrap status...")
        
        try:
            # Check if CDK toolkit stack exists
            response = self.cloudformation.describe_stacks(StackName='CDKToolkit')
            print("✅ CDK bootstrap stack found")
            
            stack_status = response['Stacks'][0]['StackStatus']
            if stack_status in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
                print(f"✅ CDK bootstrap stack is in good state: {stack_status}")
                self.test_results['cdk_bootstrap'] = {
                    'success': True,
                    'status': stack_status
                }
                return True
            else:
                print(f"⚠️  CDK bootstrap stack in unexpected state: {stack_status}")
                self.test_results['cdk_bootstrap'] = {
                    'success': False,
                    'status': stack_status,
                    'warning': 'Bootstrap stack not in expected state'
                }
                return False
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationError':
                print("⚠️  CDK bootstrap stack not found - bootstrap may be required")
                print("   Run 'cdk bootstrap' to set up CDK in this account/region")
                self.test_results['cdk_bootstrap'] = {
                    'success': False,
                    'error': 'CDK bootstrap required',
                    'recommendation': 'Run cdk bootstrap'
                }
                return False
            else:
                print(f"❌ Error checking CDK bootstrap: {e}")
                self.test_results['cdk_bootstrap'] = {
                    'success': False,
                    'error': str(e)
                }
                return False
    
    def run_basic_tests(self) -> bool:
        """Run all basic CDK deployment tests"""
        print("🚀 Starting CDK Basic Deployment Tests")
        print("=" * 50)
        
        tests = [
            ("Node.js Version Check", self.check_node_version),
            ("AWS Environment Check", self.check_aws_environment),
            ("CDK Bootstrap Check", self.test_cdk_bootstrap_check),
            ("CDK Synthesis", self.test_cdk_synthesis),
            ("Template Resource Validation", self.validate_template_resources),
            ("Deployment Validation", self.test_stack_deployment_dry_run)
        ]
        
        all_passed = True
        
        for test_name, test_func in tests:
            print(f"\n📋 Running: {test_name}")
            try:
                result = test_func()
                if not result:
                    all_passed = False
            except Exception as e:
                print(f"❌ Test {test_name} failed with exception: {e}")
                all_passed = False
        
        print("\n" + "=" * 50)
        if all_passed:
            print("🎉 All basic CDK deployment tests passed!")
        else:
            print("❌ Some tests failed. Check the output above for details.")
        
        return all_passed
    
    def generate_test_report(self) -> str:
        """Generate a detailed test report"""
        report = "# CDK Deployment Test Report\n\n"
        
        for test_name, result in self.test_results.items():
            report += f"## {test_name.replace('_', ' ').title()}\n"
            
            if result['success']:
                report += "✅ **Status**: PASSED\n\n"
            else:
                report += "❌ **Status**: FAILED\n\n"
            
            if 'error' in result:
                report += f"**Error**: {result['error']}\n\n"
            
            if 'warning' in result:
                report += f"**Warning**: {result['warning']}\n\n"
            
            # Add specific details for each test
            for key, value in result.items():
                if key not in ['success', 'error', 'warning']:
                    report += f"**{key.replace('_', ' ').title()}**: {value}\n\n"
        
        return report

def main():
    """Main test execution"""
    if len(sys.argv) > 1:
        stack_name = sys.argv[1]
    else:
        stack_name = "MA3TMainStack"
    
    tester = CDKDeploymentTester(stack_name)
    
    # Run basic tests
    success = tester.run_basic_tests()
    
    # Generate and save report
    report = tester.generate_test_report()
    report_path = os.path.join(tester.cdk_path, 'test_report.md')
    
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Detailed test report saved to: {report_path}")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()