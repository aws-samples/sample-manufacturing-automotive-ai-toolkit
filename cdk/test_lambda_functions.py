#!/usr/bin/env python3
"""
Lambda Functions and Data Population Testing Script
Tests Lambda function configurations, data population functions, and DynamoDB table population
Implements task 7.3 from the CDK conversion specification
"""

import json
import subprocess
import sys
import os
import boto3
import time
from typing import Dict, List, Optional, Any, Tuple
from botocore.exceptions import ClientError, NoCredentialsError
import uuid
from datetime import datetime

# Add the cdk directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class LambdaFunctionTester:
    """Test Lambda functions and data population functionality"""
    
    def __init__(self, stack_name: str = "MA3TMainStack"):
        self.stack_name = stack_name
        self.test_results = {}
        self.cdk_path = os.path.dirname(os.path.abspath(__file__))
        
        # Initialize AWS clients
        try:
            self.cloudformation = boto3.client('cloudformation')
            self.s3 = boto3.client('s3')
            self.dynamodb = boto3.client('dynamodb')
            self.dynamodb_resource = boto3.resource('dynamodb')
            self.lambda_client = boto3.client('lambda')
            self.logs = boto3.client('logs')
        except NoCredentialsError:
            print("❌ AWS credentials not configured. Please configure AWS credentials.")
            sys.exit(1)
    
    def get_stack_resources(self) -> Dict[str, Any]:
        """Get resources from the deployed CDK stack"""
        print("🔄 Retrieving stack resources...")
        
        try:
            # Get stack resources
            response = self.cloudformation.list_stack_resources(StackName=self.stack_name)
            resources = {}
            
            for resource in response['StackResourceSummaries']:
                resource_type = resource['ResourceType']
                logical_id = resource['LogicalResourceId']
                physical_id = resource['PhysicalResourceId']
                
                if resource_type not in resources:
                    resources[resource_type] = {}
                resources[resource_type][logical_id] = physical_id
            
            # Get stack outputs
            stack_response = self.cloudformation.describe_stacks(StackName=self.stack_name)
            outputs = {}
            
            if 'Outputs' in stack_response['Stacks'][0]:
                for output in stack_response['Stacks'][0]['Outputs']:
                    outputs[output['OutputKey']] = output['OutputValue']
            
            print(f"✅ Retrieved {len(resources)} resource types from stack")
            
            self.test_results['stack_resources'] = {
                'success': True,
                'resources': resources,
                'outputs': outputs
            }
            
            return {'resources': resources, 'outputs': outputs}
            
        except ClientError as e:
            print(f"❌ Failed to retrieve stack resources: {e}")
            self.test_results['stack_resources'] = {
                'success': False,
                'error': str(e)
            }
            return {'resources': {}, 'outputs': {}}
    
    def test_lambda_function_configurations(self, resources: Dict[str, Any]) -> bool:
        """Test that all Lambda functions are created with correct configurations"""
        print("🔄 Testing Lambda function configurations...")
        
        lambda_functions = resources.get('AWS::Lambda::Function', {})
        
        if not lambda_functions:
            print("❌ No Lambda functions found in stack")
            self.test_results['lambda_configurations'] = {
                'success': False,
                'error': 'No Lambda functions found'
            }
            return False
        
        print(f"📊 Found {len(lambda_functions)} Lambda functions")
        
        function_tests = {}
        all_passed = True
        
        for logical_id, function_name in lambda_functions.items():
            print(f"  🔍 Testing function: {function_name}")
            
            try:
                # Get function configuration
                response = self.lambda_client.get_function(FunctionName=function_name)
                config = response['Configuration']
                
                # Test basic configuration
                test_result = {
                    'function_name': function_name,
                    'runtime': config.get('Runtime'),
                    'handler': config.get('Handler'),
                    'timeout': config.get('Timeout'),
                    'memory_size': config.get('MemorySize'),
                    'environment_variables': config.get('Environment', {}).get('Variables', {}),
                    'role': config.get('Role'),
                    'state': config.get('State'),
                    'last_modified': config.get('LastModified')
                }
                
                # Validate configuration
                issues = []
                
                # Check runtime
                if not test_result['runtime']:
                    issues.append("Missing runtime")
                elif not test_result['runtime'].startswith('python'):
                    issues.append(f"Unexpected runtime: {test_result['runtime']}")
                
                # Check handler
                if not test_result['handler']:
                    issues.append("Missing handler")
                
                # Check timeout (should be reasonable)
                if test_result['timeout'] and test_result['timeout'] > 900:
                    issues.append(f"Timeout too high: {test_result['timeout']}s")
                
                # Check memory size
                if test_result['memory_size'] and test_result['memory_size'] < 128:
                    issues.append(f"Memory size too low: {test_result['memory_size']}MB")
                
                # Check state
                if test_result['state'] != 'Active':
                    issues.append(f"Function not active: {test_result['state']}")
                
                # Check environment variables
                env_vars = test_result['environment_variables']
                expected_env_patterns = ['TABLE', 'BUCKET']
                has_expected_env = any(
                    any(pattern in key.upper() for pattern in expected_env_patterns)
                    for key in env_vars.keys()
                )
                
                if not has_expected_env:
                    issues.append("Missing expected environment variables (TABLE or BUCKET)")
                
                test_result['issues'] = issues
                test_result['passed'] = len(issues) == 0
                
                if test_result['passed']:
                    print(f"    ✅ {function_name} configuration valid")
                else:
                    print(f"    ❌ {function_name} has issues: {', '.join(issues)}")
                    all_passed = False
                
                function_tests[logical_id] = test_result
                
            except ClientError as e:
                print(f"    ❌ Failed to get configuration for {function_name}: {e}")
                function_tests[logical_id] = {
                    'function_name': function_name,
                    'error': str(e),
                    'passed': False
                }
                all_passed = False
        
        self.test_results['lambda_configurations'] = {
            'success': all_passed,
            'functions_tested': len(function_tests),
            'functions_passed': sum(1 for t in function_tests.values() if t.get('passed', False)),
            'function_details': function_tests
        }
        
        return all_passed
    
    def test_dynamodb_tables(self, resources: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
        """Test DynamoDB table configurations and return table mapping"""
        print("🔄 Testing DynamoDB table configurations...")
        
        dynamodb_tables = resources.get('AWS::DynamoDB::Table', {})
        
        if not dynamodb_tables:
            print("❌ No DynamoDB tables found in stack")
            self.test_results['dynamodb_tables'] = {
                'success': False,
                'error': 'No DynamoDB tables found'
            }
            return False, {}
        
        print(f"📊 Found {len(dynamodb_tables)} DynamoDB tables")
        
        table_tests = {}
        table_mapping = {}
        all_passed = True
        
        for logical_id, table_name in dynamodb_tables.items():
            print(f"  🔍 Testing table: {table_name}")
            table_mapping[logical_id] = table_name
            
            try:
                # Get table description
                response = self.dynamodb.describe_table(TableName=table_name)
                table_desc = response['Table']
                
                test_result = {
                    'table_name': table_name,
                    'status': table_desc.get('TableStatus'),
                    'item_count': table_desc.get('ItemCount', 0),
                    'table_size_bytes': table_desc.get('TableSizeBytes', 0),
                    'key_schema': table_desc.get('KeySchema', []),
                    'attribute_definitions': table_desc.get('AttributeDefinitions', []),
                    'billing_mode': table_desc.get('BillingModeSummary', {}).get('BillingMode'),
                    'creation_date': table_desc.get('CreationDateTime')
                }
                
                # Validate table configuration
                issues = []
                
                # Check status
                if test_result['status'] != 'ACTIVE':
                    issues.append(f"Table not active: {test_result['status']}")
                
                # Check key schema
                if not test_result['key_schema']:
                    issues.append("Missing key schema")
                else:
                    # Ensure there's at least a partition key
                    has_partition_key = any(
                        key.get('KeyType') == 'HASH' 
                        for key in test_result['key_schema']
                    )
                    if not has_partition_key:
                        issues.append("Missing partition key")
                
                # Check attribute definitions
                if not test_result['attribute_definitions']:
                    issues.append("Missing attribute definitions")
                
                test_result['issues'] = issues
                test_result['passed'] = len(issues) == 0
                
                if test_result['passed']:
                    print(f"    ✅ {table_name} configuration valid")
                else:
                    print(f"    ❌ {table_name} has issues: {', '.join(issues)}")
                    all_passed = False
                
                table_tests[logical_id] = test_result
                
            except ClientError as e:
                print(f"    ❌ Failed to describe table {table_name}: {e}")
                table_tests[logical_id] = {
                    'table_name': table_name,
                    'error': str(e),
                    'passed': False
                }
                all_passed = False
        
        self.test_results['dynamodb_tables'] = {
            'success': all_passed,
            'tables_tested': len(table_tests),
            'tables_passed': sum(1 for t in table_tests.values() if t.get('passed', False)),
            'table_details': table_tests
        }
        
        return all_passed, table_mapping
    
    def test_lambda_function_invocation(self, resources: Dict[str, Any]) -> bool:
        """Test Lambda function invocation with sample payloads"""
        print("🔄 Testing Lambda function invocation...")
        
        lambda_functions = resources.get('AWS::Lambda::Function', {})
        
        if not lambda_functions:
            print("❌ No Lambda functions to test")
            return False
        
        invocation_tests = {}
        all_passed = True
        
        # Define test payloads for different function types
        test_payloads = {
            'dealer': {
                'dealer_id': 'TEST_DEALER_001'
            },
            'parts': {
                'part_number': 'TEST_PART_001'
            },
            'warranty': {
                'vin': 'TEST_VIN_12345'
            },
            'appointment': {
                'dealer_id': 'TEST_DEALER_001',
                'customer_name': 'Test Customer',
                'appointment_date': '2024-01-15',
                'service_type': 'Maintenance'
            },
            'slots': {
                'dealer_id': 'TEST_DEALER_001',
                'date': '2024-01-15'
            }
        }
        
        for logical_id, function_name in lambda_functions.items():
            print(f"  🔍 Testing invocation: {function_name}")
            
            # Determine appropriate test payload
            payload = {'test': True}
            for key, test_payload in test_payloads.items():
                if key.lower() in function_name.lower():
                    payload = test_payload
                    break
            
            try:
                # Invoke function
                response = self.lambda_client.invoke(
                    FunctionName=function_name,
                    InvocationType='RequestResponse',
                    Payload=json.dumps(payload)
                )
                
                # Parse response
                response_payload = json.loads(response['Payload'].read())
                
                test_result = {
                    'function_name': function_name,
                    'status_code': response.get('StatusCode'),
                    'payload_used': payload,
                    'response_payload': response_payload,
                    'execution_duration': response.get('ExecutionDuration'),
                    'billed_duration': response.get('BilledDuration'),
                    'memory_used': response.get('MemoryUsed'),
                    'log_result': response.get('LogResult')
                }
                
                # Validate response
                issues = []
                
                if test_result['status_code'] != 200:
                    issues.append(f"HTTP status code: {test_result['status_code']}")
                
                # Check if response has expected structure
                if isinstance(response_payload, dict):
                    if 'errorMessage' in response_payload:
                        issues.append(f"Function error: {response_payload['errorMessage']}")
                    elif 'statusCode' in response_payload:
                        # Lambda function returned HTTP-like response
                        if response_payload['statusCode'] >= 400:
                            issues.append(f"Function returned error status: {response_payload['statusCode']}")
                
                test_result['issues'] = issues
                test_result['passed'] = len(issues) == 0
                
                if test_result['passed']:
                    print(f"    ✅ {function_name} invocation successful")
                else:
                    print(f"    ❌ {function_name} invocation issues: {', '.join(issues)}")
                    all_passed = False
                
                invocation_tests[logical_id] = test_result
                
            except Exception as e:
                print(f"    ❌ Failed to invoke {function_name}: {e}")
                invocation_tests[logical_id] = {
                    'function_name': function_name,
                    'error': str(e),
                    'passed': False
                }
                all_passed = False
        
        self.test_results['lambda_invocations'] = {
            'success': all_passed,
            'functions_tested': len(invocation_tests),
            'functions_passed': sum(1 for t in invocation_tests.values() if t.get('passed', False)),
            'invocation_details': invocation_tests
        }
        
        return all_passed
    
    def test_data_population_functions(self, resources: Dict[str, Any]) -> bool:
        """Test data population functions and custom resources"""
        print("🔄 Testing data population functions...")
        
        lambda_functions = resources.get('AWS::Lambda::Function', {})
        
        # Identify data population functions
        data_functions = {}
        for logical_id, function_name in lambda_functions.items():
            # Check if this is a data population function
            data_indicators = [
                'insert', 'populate', 'sample', 'data-loader', 
                'SampleDataFunction', 'Insert', 'Populate', 'DataFunction'
            ]
            
            if any(indicator.lower() in function_name.lower() for indicator in data_indicators):
                data_functions[logical_id] = function_name
        
        print(f"📊 Found {len(data_functions)} data population functions")
        
        if not data_functions:
            print("ℹ️  No data population functions found - this may be expected")
            self.test_results['data_population'] = {
                'success': True,
                'functions_tested': 0,
                'note': 'No data population functions found'
            }
            return True
        
        data_tests = {}
        all_passed = True
        
        for logical_id, function_name in data_functions.items():
            print(f"  🔍 Testing data function: {function_name}")
            
            try:
                # Test with CloudFormation custom resource event
                custom_resource_event = {
                    'RequestType': 'Create',
                    'ResponseURL': 'https://httpbin.org/put',  # Test URL
                    'StackId': f'arn:aws:cloudformation:us-east-1:123456789012:stack/{self.stack_name}/test',
                    'RequestId': str(uuid.uuid4()),
                    'LogicalResourceId': 'TestDataPopulation',
                    'ResourceType': 'Custom::DataPopulation'
                }
                
                # Invoke function
                response = self.lambda_client.invoke(
                    FunctionName=function_name,
                    InvocationType='RequestResponse',
                    Payload=json.dumps(custom_resource_event)
                )
                
                response_payload = json.loads(response['Payload'].read())
                
                test_result = {
                    'function_name': function_name,
                    'status_code': response.get('StatusCode'),
                    'response_payload': response_payload,
                    'execution_duration': response.get('ExecutionDuration')
                }
                
                # Validate response
                issues = []
                
                if test_result['status_code'] != 200:
                    issues.append(f"HTTP status code: {test_result['status_code']}")
                
                if isinstance(response_payload, dict) and 'errorMessage' in response_payload:
                    issues.append(f"Function error: {response_payload['errorMessage']}")
                
                test_result['issues'] = issues
                test_result['passed'] = len(issues) == 0
                
                if test_result['passed']:
                    print(f"    ✅ {function_name} data population test successful")
                else:
                    print(f"    ❌ {function_name} data population issues: {', '.join(issues)}")
                    all_passed = False
                
                data_tests[logical_id] = test_result
                
            except Exception as e:
                print(f"    ❌ Failed to test data function {function_name}: {e}")
                data_tests[logical_id] = {
                    'function_name': function_name,
                    'error': str(e),
                    'passed': False
                }
                all_passed = False
        
        self.test_results['data_population'] = {
            'success': all_passed,
            'functions_tested': len(data_tests),
            'functions_passed': sum(1 for t in data_tests.values() if t.get('passed', False)),
            'data_function_details': data_tests
        }
        
        return all_passed
    
    def validate_sample_data_population(self, table_mapping: Dict[str, str]) -> bool:
        """Validate that DynamoDB tables are populated with sample data"""
        print("🔄 Validating DynamoDB sample data population...")
        
        if not table_mapping:
            print("❌ No tables to validate")
            return False
        
        validation_tests = {}
        all_passed = True
        
        for logical_id, table_name in table_mapping.items():
            print(f"  🔍 Checking data in table: {table_name}")
            
            try:
                # Scan table to check for data
                table = self.dynamodb_resource.Table(table_name)
                
                # Get a small sample of items
                response = table.scan(Limit=10)
                items = response.get('Items', [])
                item_count = response.get('Count', 0)
                
                # Get approximate total count
                table_desc = self.dynamodb.describe_table(TableName=table_name)
                total_items = table_desc['Table'].get('ItemCount', 0)
                
                test_result = {
                    'table_name': table_name,
                    'sample_items': items,
                    'sample_count': item_count,
                    'total_items_approx': total_items,
                    'has_data': item_count > 0 or total_items > 0
                }
                
                # Validate data presence
                issues = []
                
                if not test_result['has_data']:
                    # Check if this table should have sample data
                    # Some tables might be empty by design
                    expected_data_tables = [
                        'dealer', 'parts', 'warranty', 'sample'
                    ]
                    
                    should_have_data = any(
                        keyword in table_name.lower() 
                        for keyword in expected_data_tables
                    )
                    
                    if should_have_data:
                        issues.append("Table appears to be empty but should contain sample data")
                    else:
                        # Table is empty but that might be expected
                        test_result['note'] = "Table is empty - this may be expected for this table type"
                
                # Validate sample data structure if present
                if items:
                    sample_item = items[0]
                    if not isinstance(sample_item, dict) or not sample_item:
                        issues.append("Sample data has unexpected structure")
                    else:
                        test_result['sample_keys'] = list(sample_item.keys())
                
                test_result['issues'] = issues
                test_result['passed'] = len(issues) == 0
                
                if test_result['passed']:
                    if test_result['has_data']:
                        print(f"    ✅ {table_name} contains data ({total_items} items)")
                    else:
                        print(f"    ✅ {table_name} validation passed (empty table)")
                else:
                    print(f"    ❌ {table_name} validation issues: {', '.join(issues)}")
                    all_passed = False
                
                validation_tests[logical_id] = test_result
                
            except Exception as e:
                print(f"    ❌ Failed to validate data in {table_name}: {e}")
                validation_tests[logical_id] = {
                    'table_name': table_name,
                    'error': str(e),
                    'passed': False
                }
                all_passed = False
        
        self.test_results['sample_data_validation'] = {
            'success': all_passed,
            'tables_tested': len(validation_tests),
            'tables_passed': sum(1 for t in validation_tests.values() if t.get('passed', False)),
            'validation_details': validation_tests
        }
        
        return all_passed
    
    def run_all_tests(self) -> bool:
        """Run all Lambda function and data population tests"""
        print("🚀 Starting Lambda Functions and Data Population Tests")
        print("=" * 60)
        
        # Get stack resources first
        stack_info = self.get_stack_resources()
        if not self.test_results.get('stack_resources', {}).get('success', False):
            print("❌ Cannot proceed without stack resources")
            return False
        
        resources = stack_info['resources']
        
        tests = [
            ("Lambda Function Configurations", lambda: self.test_lambda_function_configurations(resources)),
            ("DynamoDB Table Configurations", lambda: self.test_dynamodb_tables(resources)),
            ("Lambda Function Invocations", lambda: self.test_lambda_function_invocation(resources)),
            ("Data Population Functions", lambda: self.test_data_population_functions(resources)),
        ]
        
        all_passed = True
        table_mapping = {}
        
        for test_name, test_func in tests:
            print(f"\n📋 Running: {test_name}")
            try:
                if test_name == "DynamoDB Table Configurations":
                    result, table_mapping = test_func()
                else:
                    result = test_func()
                
                if not result:
                    all_passed = False
            except Exception as e:
                print(f"❌ Test {test_name} failed with exception: {e}")
                all_passed = False
        
        # Run sample data validation if we have tables
        if table_mapping:
            print(f"\n📋 Running: Sample Data Validation")
            try:
                result = self.validate_sample_data_population(table_mapping)
                if not result:
                    all_passed = False
            except Exception as e:
                print(f"❌ Sample Data Validation failed with exception: {e}")
                all_passed = False
        
        print("\n" + "=" * 60)
        if all_passed:
            print("🎉 All Lambda function and data population tests passed!")
        else:
            print("❌ Some tests failed. Check the output above for details.")
        
        return all_passed
    
    def generate_test_report(self) -> str:
        """Generate a detailed test report"""
        report = "# Lambda Functions and Data Population Test Report\n\n"
        report += f"**Test Date**: {datetime.now().isoformat()}\n"
        report += f"**Stack Name**: {self.stack_name}\n\n"
        
        # Summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result.get('success', False))
        
        report += f"## Summary\n\n"
        report += f"- **Total Test Categories**: {total_tests}\n"
        report += f"- **Passed**: {passed_tests}\n"
        report += f"- **Failed**: {total_tests - passed_tests}\n\n"
        
        # Detailed results
        for test_name, result in self.test_results.items():
            report += f"## {test_name.replace('_', ' ').title()}\n\n"
            
            if result['success']:
                report += "✅ **Status**: PASSED\n\n"
            else:
                report += "❌ **Status**: FAILED\n\n"
            
            if 'error' in result:
                report += f"**Error**: {result['error']}\n\n"
            
            # Add specific metrics
            if 'functions_tested' in result:
                report += f"**Functions Tested**: {result['functions_tested']}\n"
                report += f"**Functions Passed**: {result.get('functions_passed', 0)}\n\n"
            
            if 'tables_tested' in result:
                report += f"**Tables Tested**: {result['tables_tested']}\n"
                report += f"**Tables Passed**: {result.get('tables_passed', 0)}\n\n"
            
            # Add detailed information for specific test types
            if test_name == 'lambda_configurations' and 'function_details' in result:
                report += "### Function Details\n\n"
                for func_id, func_detail in result['function_details'].items():
                    status = "✅" if func_detail.get('passed', False) else "❌"
                    report += f"- {status} **{func_detail.get('function_name', func_id)}**\n"
                    if func_detail.get('issues'):
                        report += f"  - Issues: {', '.join(func_detail['issues'])}\n"
                    report += f"  - Runtime: {func_detail.get('runtime', 'N/A')}\n"
                    report += f"  - Memory: {func_detail.get('memory_size', 'N/A')} MB\n"
                    report += f"  - Timeout: {func_detail.get('timeout', 'N/A')} seconds\n\n"
            
            if test_name == 'sample_data_validation' and 'validation_details' in result:
                report += "### Data Validation Details\n\n"
                for table_id, table_detail in result['validation_details'].items():
                    status = "✅" if table_detail.get('passed', False) else "❌"
                    report += f"- {status} **{table_detail.get('table_name', table_id)}**\n"
                    report += f"  - Items: ~{table_detail.get('total_items_approx', 0)}\n"
                    if table_detail.get('sample_keys'):
                        report += f"  - Sample Keys: {', '.join(table_detail['sample_keys'])}\n"
                    if table_detail.get('issues'):
                        report += f"  - Issues: {', '.join(table_detail['issues'])}\n"
                    report += "\n"
        
        return report

def main():
    """Main test execution"""
    if len(sys.argv) > 1:
        stack_name = sys.argv[1]
    else:
        stack_name = "MA3TMainStack"
    
    print(f"Testing Lambda functions and data population for stack: {stack_name}")
    
    tester = LambdaFunctionTester(stack_name)
    
    # Run all tests
    success = tester.run_all_tests()
    
    # Generate and save report
    report = tester.generate_test_report()
    report_path = os.path.join(tester.cdk_path, 'lambda_test_report.md')
    
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Detailed test report saved to: {report_path}")
    
    # Print summary
    print(f"\n📊 Test Summary:")
    total_categories = len(tester.test_results)
    passed_categories = sum(1 for result in tester.test_results.values() if result.get('success', False))
    
    print(f"   Test Categories: {passed_categories}/{total_categories} passed")
    
    # Print function and table counts
    if 'lambda_configurations' in tester.test_results:
        func_result = tester.test_results['lambda_configurations']
        print(f"   Lambda Functions: {func_result.get('functions_passed', 0)}/{func_result.get('functions_tested', 0)} passed")
    
    if 'dynamodb_tables' in tester.test_results:
        table_result = tester.test_results['dynamodb_tables']
        print(f"   DynamoDB Tables: {table_result.get('tables_passed', 0)}/{table_result.get('tables_tested', 0)} passed")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()