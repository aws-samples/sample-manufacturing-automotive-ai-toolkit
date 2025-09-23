#!/usr/bin/env python3
"""
Local Lambda Function Testing Script
Tests Lambda function code and configurations without requiring AWS deployment
Implements local testing for task 7.3 from the CDK conversion specification
"""

import json
import sys
import os
from typing import Dict, List, Optional, Any
import importlib.util
from unittest.mock import Mock, patch
import tempfile

# Add the cdk directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class LocalLambdaTester:
    """Test Lambda functions locally without AWS deployment"""
    
    def __init__(self):
        self.test_results = {}
        self.cdk_path = os.path.dirname(os.path.abspath(__file__))
    
    def test_compute_construct_creation(self) -> bool:
        """Test that the ComputeConstruct can be created and generates Lambda functions"""
        print("🔄 Testing ComputeConstruct creation...")
        
        try:
            # Import required modules
            from stacks.constructs.compute import ComputeConstruct
            from constructs import Construct
            import aws_cdk as cdk
            from aws_cdk import aws_dynamodb as dynamodb, aws_iam as iam, aws_s3 as s3
            
            # Create a mock CDK app and stack for testing
            app = cdk.App()
            stack = cdk.Stack(app, "TestStack")
            
            # Create mock dependencies
            mock_tables = {
                'dealer-data': Mock(spec=dynamodb.Table),
                'parts-data': Mock(spec=dynamodb.Table),
                'warranty-data': Mock(spec=dynamodb.Table),
                'appointment-data': Mock(spec=dynamodb.Table)
            }
            
            # Set table names
            for table_name, table_mock in mock_tables.items():
                table_mock.table_name = table_name
            
            mock_role = Mock(spec=iam.Role)
            mock_role.role_arn = "arn:aws:iam::123456789012:role/test-role"
            
            mock_bucket = Mock(spec=s3.Bucket)
            mock_bucket.bucket_name = "test-bucket"
            
            # Create ComputeConstruct
            compute_construct = ComputeConstruct(
                stack, "TestCompute",
                tables=mock_tables,
                lambda_role=mock_role,
                resource_bucket=mock_bucket
            )
            
            # Test that functions were created
            business_functions = compute_construct.business_functions
            data_functions = compute_construct.data_functions
            
            print(f"  📊 Business functions created: {len(business_functions)}")
            print(f"  📊 Data functions created: {len(data_functions)}")
            
            # Validate function creation
            issues = []
            
            if not business_functions:
                issues.append("No business functions created")
            
            # Check for expected business functions
            expected_business_functions = [
                'get-dealer-data', 'get-parts-for-dtc', 'GetWarrantyData',
                'BookAppointment', 'get-dealer-appointment-slots'
            ]
            
            for expected_func in expected_business_functions:
                if expected_func not in business_functions:
                    issues.append(f"Missing expected business function: {expected_func}")
            
            # Test function properties
            for func_name, func in business_functions.items():
                if not hasattr(func, 'function_name'):
                    issues.append(f"Function {func_name} missing function_name property")
            
            test_result = {
                'business_functions_count': len(business_functions),
                'data_functions_count': len(data_functions),
                'business_function_names': list(business_functions.keys()),
                'data_function_names': list(data_functions.keys()),
                'issues': issues,
                'passed': len(issues) == 0
            }
            
            if test_result['passed']:
                print("  ✅ ComputeConstruct creation successful")
                for func_name in business_functions.keys():
                    print(f"    - {func_name}")
            else:
                print(f"  ❌ ComputeConstruct creation issues: {', '.join(issues)}")
            
            self.test_results['compute_construct'] = test_result
            return test_result['passed']
            
        except Exception as e:
            print(f"❌ ComputeConstruct creation failed: {e}")
            import traceback
            traceback.print_exc()
            self.test_results['compute_construct'] = {
                'error': str(e),
                'passed': False
            }
            return False
    
    def test_lambda_function_code(self) -> bool:
        """Test Lambda function code execution locally"""
        print("🔄 Testing Lambda function code execution...")
        
        try:
            from stacks.constructs.compute import ComputeConstruct
            
            # Create a temporary ComputeConstruct to get function code
            compute = ComputeConstruct.__new__(ComputeConstruct)
            
            # Test individual function code methods
            function_tests = {}
            
            # Test dealer data function
            dealer_code = compute._get_dealer_data_code()
            dealer_test = self._test_function_code(
                dealer_code, 
                {'dealer_id': 'TEST_DEALER_001'},
                'get_dealer_data'
            )
            function_tests['dealer_data'] = dealer_test
            
            # Test parts function
            parts_code = compute._get_parts_code()
            parts_test = self._test_function_code(
                parts_code,
                {'part_number': 'TEST_PART_001'},
                'get_parts_for_dtc'
            )
            function_tests['parts_data'] = parts_test
            
            # Test warranty function
            warranty_code = compute._get_warranty_code()
            warranty_test = self._test_function_code(
                warranty_code,
                {'vin': 'TEST_VIN_12345'},
                'get_warranty_data'
            )
            function_tests['warranty_data'] = warranty_test
            
            # Test appointment booking function
            appointment_code = compute._get_appointment_code()
            appointment_test = self._test_function_code(
                appointment_code,
                {
                    'dealer_id': 'TEST_DEALER_001',
                    'customer_name': 'Test Customer',
                    'appointment_date': '2024-01-15',
                    'service_type': 'Maintenance'
                },
                'book_appointment'
            )
            function_tests['appointment_booking'] = appointment_test
            
            # Test appointment slots function
            slots_code = compute._get_appointment_slots_code()
            slots_test = self._test_function_code(
                slots_code,
                {'dealer_id': 'TEST_DEALER_001'},
                'get_appointment_slots'
            )
            function_tests['appointment_slots'] = slots_test
            
            # Summarize results
            total_tests = len(function_tests)
            passed_tests = sum(1 for test in function_tests.values() if test['passed'])
            
            all_passed = passed_tests == total_tests
            
            print(f"  📊 Function code tests: {passed_tests}/{total_tests} passed")
            
            for func_name, test_result in function_tests.items():
                status = "✅" if test_result['passed'] else "❌"
                print(f"    {status} {func_name}")
                if not test_result['passed'] and 'error' in test_result:
                    print(f"      Error: {test_result['error']}")
            
            self.test_results['lambda_code'] = {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'function_tests': function_tests,
                'passed': all_passed
            }
            
            return all_passed
            
        except Exception as e:
            print(f"❌ Lambda function code testing failed: {e}")
            import traceback
            traceback.print_exc()
            self.test_results['lambda_code'] = {
                'error': str(e),
                'passed': False
            }
            return False
    
    def _test_function_code(self, code: str, test_event: Dict, handler_name: str) -> Dict[str, Any]:
        """Test individual Lambda function code"""
        try:
            # Create a temporary module to execute the code
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # Load the module
            spec = importlib.util.spec_from_file_location("test_lambda", temp_file)
            module = importlib.util.module_from_spec(spec)
            
            # Mock AWS services
            with patch('boto3.resource') as mock_resource, \
                 patch('boto3.client') as mock_client, \
                 patch.dict(os.environ, {
                     'DEALER_DATA_TABLE': 'test-dealer-table',
                     'PARTS_DATA_TABLE': 'test-parts-table',
                     'WARRANTY_DATA_TABLE': 'test-warranty-table',
                     'APPOINTMENT_DATA_TABLE': 'test-appointment-table'
                 }):
                
                # Configure mock DynamoDB responses
                mock_table = Mock()
                mock_table.get_item.return_value = {
                    'Item': {'test_key': 'test_value', 'status': 'active'}
                }
                mock_table.put_item.return_value = {}
                mock_resource.return_value.Table.return_value = mock_table
                
                # Execute the module
                spec.loader.exec_module(module)
                
                # Get the handler function
                handler = getattr(module, 'handler', None)
                if not handler:
                    # Try alternative handler names
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if callable(attr) and attr_name in handler_name:
                            handler = attr
                            break
                
                if not handler:
                    return {
                        'error': f'Handler function not found in code',
                        'passed': False
                    }
                
                # Create mock context
                mock_context = Mock()
                mock_context.function_name = f'test-{handler_name}'
                mock_context.aws_request_id = 'test-request-id'
                
                # Call the handler
                result = handler(test_event, mock_context)
                
                # Validate result
                issues = []
                
                if not isinstance(result, dict):
                    issues.append(f"Handler returned {type(result)}, expected dict")
                elif 'statusCode' in result:
                    # HTTP-style response
                    if result['statusCode'] >= 400:
                        issues.append(f"Handler returned error status: {result['statusCode']}")
                elif 'errorMessage' in result:
                    issues.append(f"Handler returned error: {result['errorMessage']}")
                
                # Clean up
                os.unlink(temp_file)
                
                return {
                    'result': result,
                    'issues': issues,
                    'passed': len(issues) == 0
                }
                
        except Exception as e:
            # Clean up on error
            if 'temp_file' in locals():
                try:
                    os.unlink(temp_file)
                except:
                    pass
            
            return {
                'error': str(e),
                'passed': False
            }
    
    def test_storage_construct_creation(self) -> bool:
        """Test that the StorageConstruct can be created and generates DynamoDB tables"""
        print("🔄 Testing StorageConstruct creation...")
        
        try:
            from stacks.constructs.storage import StorageConstruct
            import aws_cdk as cdk
            
            # Create a mock CDK app and stack for testing
            app = cdk.App()
            stack = cdk.Stack(app, "TestStack")
            
            # Create StorageConstruct
            storage_construct = StorageConstruct(
                stack, "TestStorage",
                s3_bucket_name="test-bucket"
            )
            
            # Test that resources were created
            bucket = storage_construct.resource_bucket
            tables = storage_construct.tables
            
            print(f"  📊 S3 bucket created: {bucket is not None}")
            print(f"  📊 DynamoDB tables created: {len(tables)}")
            
            # Validate resource creation
            issues = []
            
            if not bucket:
                issues.append("S3 bucket not created")
            
            if not tables:
                issues.append("No DynamoDB tables created")
            
            # Check for expected tables
            expected_tables = ['dealer-data', 'parts-data', 'warranty-data', 'appointment-data']
            
            for expected_table in expected_tables:
                if expected_table not in tables:
                    issues.append(f"Missing expected table: {expected_table}")
            
            test_result = {
                'bucket_created': bucket is not None,
                'tables_count': len(tables),
                'table_names': list(tables.keys()),
                'issues': issues,
                'passed': len(issues) == 0
            }
            
            if test_result['passed']:
                print("  ✅ StorageConstruct creation successful")
                for table_name in tables.keys():
                    print(f"    - Table: {table_name}")
            else:
                print(f"  ❌ StorageConstruct creation issues: {', '.join(issues)}")
            
            self.test_results['storage_construct'] = test_result
            return test_result['passed']
            
        except Exception as e:
            print(f"❌ StorageConstruct creation failed: {e}")
            import traceback
            traceback.print_exc()
            self.test_results['storage_construct'] = {
                'error': str(e),
                'passed': False
            }
            return False
    
    def test_environment_variable_configuration(self) -> bool:
        """Test that Lambda functions get proper environment variable configuration"""
        print("🔄 Testing environment variable configuration...")
        
        try:
            from stacks.constructs.compute import ComputeConstruct
            
            # Create a temporary ComputeConstruct to test environment variable building
            compute = ComputeConstruct.__new__(ComputeConstruct)
            
            # Mock tables
            mock_tables = {
                'dealer-data': Mock(),
                'parts-data': Mock(),
                'warranty-data': Mock(),
                'appointment-data': Mock()
            }
            
            for table_name, table_mock in mock_tables.items():
                table_mock.table_name = f"test-{table_name}"
            
            compute.tables = mock_tables
            
            # Mock S3 bucket
            mock_bucket = Mock()
            mock_bucket.bucket_name = "test-resource-bucket"
            compute.resource_bucket = mock_bucket
            
            # Test environment variable building
            env_vars = compute._build_environment_variables({}, 'test-function')
            
            print(f"  📊 Environment variables generated: {len(env_vars)}")
            
            # Validate environment variables
            issues = []
            
            # Check for table environment variables
            expected_table_vars = [
                'DEALER_DATA_TABLE', 'PARTS_DATA_TABLE', 
                'WARRANTY_DATA_TABLE', 'APPOINTMENT_DATA_TABLE'
            ]
            
            for expected_var in expected_table_vars:
                if expected_var not in env_vars:
                    issues.append(f"Missing environment variable: {expected_var}")
                else:
                    print(f"    ✅ {expected_var}: {env_vars[expected_var]}")
            
            # Check for S3 bucket variable
            if 'S3_BUCKET_NAME' not in env_vars:
                issues.append("Missing S3_BUCKET_NAME environment variable")
            else:
                print(f"    ✅ S3_BUCKET_NAME: {env_vars['S3_BUCKET_NAME']}")
            
            test_result = {
                'env_vars_count': len(env_vars),
                'env_vars': env_vars,
                'issues': issues,
                'passed': len(issues) == 0
            }
            
            if test_result['passed']:
                print("  ✅ Environment variable configuration successful")
            else:
                print(f"  ❌ Environment variable issues: {', '.join(issues)}")
            
            self.test_results['environment_variables'] = test_result
            return test_result['passed']
            
        except Exception as e:
            print(f"❌ Environment variable testing failed: {e}")
            import traceback
            traceback.print_exc()
            self.test_results['environment_variables'] = {
                'error': str(e),
                'passed': False
            }
            return False
    
    def run_all_tests(self) -> bool:
        """Run all local Lambda function tests"""
        print("🚀 Starting Local Lambda Function Tests")
        print("=" * 50)
        
        tests = [
            ("Storage Construct Creation", self.test_storage_construct_creation),
            ("Compute Construct Creation", self.test_compute_construct_creation),
            ("Environment Variable Configuration", self.test_environment_variable_configuration),
            ("Lambda Function Code Execution", self.test_lambda_function_code),
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
            print("🎉 All local Lambda function tests passed!")
        else:
            print("❌ Some tests failed. Check the output above for details.")
        
        return all_passed
    
    def generate_test_report(self) -> str:
        """Generate a detailed test report"""
        report = "# Local Lambda Function Test Report\n\n"
        
        # Summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result.get('passed', False))
        
        report += f"## Summary\n\n"
        report += f"- **Total Test Categories**: {total_tests}\n"
        report += f"- **Passed**: {passed_tests}\n"
        report += f"- **Failed**: {total_tests - passed_tests}\n\n"
        
        # Detailed results
        for test_name, result in self.test_results.items():
            report += f"## {test_name.replace('_', ' ').title()}\n\n"
            
            if result['passed']:
                report += "✅ **Status**: PASSED\n\n"
            else:
                report += "❌ **Status**: FAILED\n\n"
            
            if 'error' in result:
                report += f"**Error**: {result['error']}\n\n"
            
            # Add specific details
            for key, value in result.items():
                if key not in ['passed', 'error']:
                    if isinstance(value, (list, dict)) and len(str(value)) > 100:
                        report += f"**{key.replace('_', ' ').title()}**: [Complex data - see detailed output]\n"
                    else:
                        report += f"**{key.replace('_', ' ').title()}**: {value}\n"
            
            report += "\n"
        
        return report

def main():
    """Main test execution"""
    print("Testing Lambda functions locally (no AWS deployment required)")
    
    tester = LocalLambdaTester()
    
    # Run all tests
    success = tester.run_all_tests()
    
    # Generate and save report
    report = tester.generate_test_report()
    report_path = os.path.join(tester.cdk_path, 'local_lambda_test_report.md')
    
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Detailed test report saved to: {report_path}")
    
    # Print summary
    print(f"\n📊 Test Summary:")
    total_categories = len(tester.test_results)
    passed_categories = sum(1 for result in tester.test_results.values() if result.get('passed', False))
    
    print(f"   Test Categories: {passed_categories}/{total_categories} passed")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()