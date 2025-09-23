"""
Compute Construct for Lambda functions
"""

from aws_cdk import (
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    Duration,
    Tags,
    CustomResource,
    custom_resources as cr,
)
from constructs import Construct
from typing import Dict, Optional
import os
import sys

# Add the template loader path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 
                             'agents_catalog', 'multi_agent_collaboration', 
                             '00-vista-agents', 'cdk'))

try:
    from template_loader import load_lambda_templates
except ImportError:
    # Fallback if template loader is not available
    def load_lambda_templates():
        return {
            'lambda_functions': {},
            'sample_data_functions': {},
            'custom_resources': {}
        }


class ComputeConstruct(Construct):
    """
    Manages all Lambda functions for the MA3T application.
    """

    def __init__(self, scope: Construct, construct_id: str, 
                 tables: Dict[str, dynamodb.Table] = None,
                 lambda_role: iam.Role = None,
                 resource_bucket: Optional[s3.Bucket] = None,
                 **kwargs) -> None:
        super().__init__(scope, construct_id)
        
        self.tables = tables or {}
        self.lambda_role = lambda_role
        self.resource_bucket = resource_bucket
        
        # Load template data
        template_data = load_lambda_templates()
        
        # Create business logic Lambda functions
        self._create_business_functions(template_data.get('lambda_functions', {}))
        
        # Create data population Lambda functions
        self._create_data_functions(template_data.get('sample_data_functions', {}))
        
        # Create custom resources for data population
        self._create_custom_resources(template_data.get('custom_resources', {}))
        
        # Apply tags
        self._apply_tags()

    def _create_business_functions(self, function_definitions: Dict[str, Dict]) -> None:
        """Create business logic Lambda functions from template definitions"""
        self.business_functions: Dict[str, lambda_.Function] = {}
        
        # If no function definitions from templates, create default functions
        if not function_definitions:
            self._create_default_business_functions()
            return
        
        for function_name, function_def in function_definitions.items():
            # Skip data population functions (they're handled separately)
            if self._is_data_function(function_name):
                continue
            
            properties = function_def.get('properties', {})
            
            # Create environment variables
            environment = self._build_environment_variables(
                function_def.get('environment', {}), 
                function_name
            )
            
            # Create the Lambda function
            lambda_function = lambda_.Function(
                self, f"Function{self._sanitize_name(function_name)}",
                function_name=function_name,
                runtime=self._get_runtime(function_def.get('runtime', 'python3.9')),
                handler=properties.get('Handler', 'index.handler'),
                code=lambda_.Code.from_inline(function_def.get('code', self._get_default_code(function_name))),
                timeout=Duration.seconds(function_def.get('timeout', 300)),
                memory_size=function_def.get('memory_size', 256),
                role=self.lambda_role,
                environment=environment,
                architecture=self._get_architecture(function_def.get('architecture', 'x86_64'))
            )
            
            self.business_functions[function_name] = lambda_function

    def _create_data_functions(self, data_function_definitions: Dict[str, Dict]) -> None:
        """Create data population Lambda functions from template definitions"""
        self.data_functions: Dict[str, lambda_.Function] = {}
        
        for function_name, function_def in data_function_definitions.items():
            properties = function_def.get('properties', {})
            
            # Create environment variables for data functions
            environment = self._build_data_function_environment(function_name)
            
            # Create the data population Lambda function
            lambda_function = lambda_.Function(
                self, f"DataFunction{self._sanitize_name(function_name)}",
                function_name=function_name,
                runtime=lambda_.Runtime.PYTHON_3_9,
                handler=properties.get('Handler', 'index.handler'),
                code=lambda_.Code.from_inline(function_def.get('code', self._get_default_data_code(function_name))),
                timeout=Duration.seconds(300),
                memory_size=256,
                role=self.lambda_role,
                environment=environment
            )
            
            self.data_functions[function_name] = lambda_function

    def _create_custom_resources(self, custom_resource_definitions: Dict[str, Dict]) -> None:
        """Create custom resources for data population"""
        self.custom_resources: Dict[str, CustomResource] = {}
        
        for resource_name, resource_def in custom_resource_definitions.items():
            properties = resource_def.get('properties', {})
            service_token = properties.get('ServiceToken')
            
            # Find the corresponding Lambda function for this custom resource
            lambda_function = None
            for func_name, func in self.data_functions.items():
                if service_token and func_name in str(service_token):
                    lambda_function = func
                    break
            
            if lambda_function:
                # Create custom resource provider
                provider = cr.Provider(
                    self, f"Provider{self._sanitize_name(resource_name)}",
                    on_event_handler=lambda_function
                )
                
                # Remove ServiceToken from properties to avoid conflict
                clean_properties = {k: v for k, v in properties.items() if k != 'ServiceToken'}
                
                # Create custom resource
                custom_resource = CustomResource(
                    self, f"CustomResource{self._sanitize_name(resource_name)}",
                    service_token=provider.service_token,
                    properties=clean_properties
                )
                
                self.custom_resources[resource_name] = custom_resource

    def _create_default_business_functions(self) -> None:
        """Create default business logic functions if no template definitions are available"""
        default_functions = [
            {
                'name': 'get-dealer-data',
                'handler': 'index.get_dealer_data',
                'code': self._get_dealer_data_code()
            },
            {
                'name': 'get-parts-for-dtc',
                'handler': 'index.get_parts_for_dtc',
                'code': self._get_parts_code()
            },
            {
                'name': 'GetWarrantyData',
                'handler': 'index.get_warranty_data',
                'code': self._get_warranty_code()
            },
            {
                'name': 'BookAppointment',
                'handler': 'index.book_appointment',
                'code': self._get_appointment_code()
            },
            {
                'name': 'get-dealer-appointment-slots',
                'handler': 'index.get_appointment_slots',
                'code': self._get_appointment_slots_code()
            }
        ]
        
        for func_def in default_functions:
            environment = self._build_environment_variables({}, func_def['name'])
            
            lambda_function = lambda_.Function(
                self, f"Function{self._sanitize_name(func_def['name'])}",
                function_name=func_def['name'],
                runtime=lambda_.Runtime.PYTHON_3_9,
                handler=func_def['handler'],
                code=lambda_.Code.from_inline(func_def['code']),
                timeout=Duration.seconds(300),
                memory_size=256,
                role=self.lambda_role,
                environment=environment
            )
            
            self.business_functions[func_def['name']] = lambda_function

    def _build_environment_variables(self, template_env: Dict, function_name: str) -> Dict[str, str]:
        """Build environment variables for Lambda functions"""
        environment = {}
        
        # Add table names as environment variables
        for table_name, table in self.tables.items():
            env_var_name = f"{table_name.upper().replace('-', '_')}_TABLE"
            environment[env_var_name] = table.table_name
        
        # Add S3 bucket name if available
        if self.resource_bucket:
            environment['S3_BUCKET_NAME'] = self.resource_bucket.bucket_name
        
        # Add template-specific environment variables
        template_variables = template_env.get('Variables', {})
        for key, value in template_variables.items():
            # Handle CloudFormation references
            if isinstance(value, dict):
                if 'Ref' in value:
                    # Handle parameter references
                    if value['Ref'] in ['AWS::Region', 'AWS::AccountId']:
                        continue  # These will be handled by CDK context
                elif 'Fn::GetAtt' in value or '!GetAtt' in str(value):
                    # Handle resource references - skip for now
                    continue
            environment[key] = str(value)
        
        return environment

    def _build_data_function_environment(self, function_name: str) -> Dict[str, str]:
        """Build environment variables specifically for data population functions"""
        environment = {}
        
        # Add all table names
        for table_name, table in self.tables.items():
            env_var_name = f"{table_name.upper().replace('-', '_')}_TABLE"
            environment[env_var_name] = table.table_name
        
        return environment

    def _is_data_function(self, function_name: str) -> bool:
        """Check if a function is a data population function"""
        data_indicators = [
            'insert', 'populate', 'sample', 'data-loader', 
            'SampleDataFunction', 'Insert', 'Populate'
        ]
        
        business_indicators = [
            'GetWarrantyData', 'get-dealer-data', 'get-parts-for-dtc',
            'get-dealer-stock', 'place-parts-order', 'BookAppointment',
            'get-dealer-appointment-slots'
        ]
        
        # If it's clearly a business function, return False
        if any(indicator in function_name for indicator in business_indicators):
            return False
        
        # If it has data indicators, return True
        return any(indicator in function_name for indicator in data_indicators)

    def _get_runtime(self, runtime_string: str) -> lambda_.Runtime:
        """Convert runtime string to CDK Runtime object"""
        runtime_map = {
            'python3.9': lambda_.Runtime.PYTHON_3_9,
            'python3.8': lambda_.Runtime.PYTHON_3_8,
            'python3.10': lambda_.Runtime.PYTHON_3_10,
            'python3.11': lambda_.Runtime.PYTHON_3_11,
            'nodejs18.x': lambda_.Runtime.NODEJS_18_X,
            'nodejs20.x': lambda_.Runtime.NODEJS_20_X
        }
        return runtime_map.get(runtime_string, lambda_.Runtime.PYTHON_3_9)

    def _get_architecture(self, arch_string: str) -> lambda_.Architecture:
        """Convert architecture string to CDK Architecture object"""
        if arch_string == 'arm64':
            return lambda_.Architecture.ARM_64
        return lambda_.Architecture.X86_64

    def _sanitize_name(self, name: str) -> str:
        """Sanitize function name for use in CDK construct IDs"""
        return name.replace('-', '').replace('_', '').replace('.', '')

    def _get_default_code(self, function_name: str) -> str:
        """Get default code for business logic functions"""
        return f'''
import json
import boto3
import os

def handler(event, context):
    """
    Default handler for {function_name}
    This is a placeholder implementation.
    """
    try:
        print(f"Function {function_name} called with event: {{event}}")
        
        return {{
            'statusCode': 200,
            'body': json.dumps({{
                'message': f'Function {function_name} executed successfully',
                'event': event
            }})
        }}
    
    except Exception as e:
        print(f"Error in {function_name}: {{str(e)}}")
        return {{
            'statusCode': 500,
            'body': json.dumps({{
                'error': str(e),
                'message': f'Function {function_name} encountered an error'
            }})
        }}
'''

    def _get_default_data_code(self, function_name: str) -> str:
        """Get default code for data population functions"""
        return f'''
import json
import boto3
import os

def handler(event, context):
    """
    Data population handler for {function_name}
    """
    try:
        print(f"Data function {function_name} called with event: {{event}}")
        
        # Handle CloudFormation custom resource events
        if 'RequestType' in event:
            request_type = event['RequestType']
            if request_type in ['Create', 'Update']:
                # Populate sample data
                print(f"Populating sample data for {function_name}")
                # Add actual data population logic here
                success = populate_sample_data()
                if not success:
                    raise Exception("Failed to populate sample data")
            elif request_type == 'Delete':
                print(f"Cleanup for {function_name}")
            
            # Send response back to CloudFormation
            import urllib3
            http = urllib3.PoolManager()
            
            response_data = {{'Status': 'SUCCESS', 'Data': {{'Message': 'Success'}}}}
            
            if 'ResponseURL' in event:
                try:
                    response = http.request('PUT', event['ResponseURL'], 
                                          body=json.dumps(response_data),
                                          headers={{'Content-Type': 'application/json'}})
                    print(f"CloudFormation response sent: {{response.status}}")
                except Exception as e:
                    print(f"Failed to send CloudFormation response: {{e}}")
        
        return {{'statusCode': 200, 'body': json.dumps('Success')}}
    
    except Exception as e:
        print(f"Error in data population function: {{str(e)}}")
        
        # Send failure response to CloudFormation if applicable
        if 'RequestType' in event and 'ResponseURL' in event:
            try:
                import urllib3
                http = urllib3.PoolManager()
                response_data = {{'Status': 'FAILED', 'Reason': str(e)}}
                http.request('PUT', event['ResponseURL'], 
                           body=json.dumps(response_data),
                           headers={{'Content-Type': 'application/json'}})
            except:
                pass  # Best effort to send failure response
        
        return {{'statusCode': 500, 'body': json.dumps({{'error': str(e)}})}}

def populate_sample_data():
    """Populate sample data into DynamoDB tables"""
    try:
        dynamodb = boto3.resource('dynamodb')
        
        # Get table names from environment variables
        table_names = {{
            'dealer': os.environ.get('DEALER_DATA_TABLE'),
            'parts': os.environ.get('PARTS_DATA_TABLE'),
            'warranty': os.environ.get('WARRANTY_DATA_TABLE'),
            'appointment': os.environ.get('APPOINTMENT_DATA_TABLE')
        }}
        
        # Sample data for each table
        sample_data = {{
            'dealer': [
                {{'dealer_id': 'DEALER_001', 'name': 'Sample Dealer 1', 'location': 'City A'}},
                {{'dealer_id': 'DEALER_002', 'name': 'Sample Dealer 2', 'location': 'City B'}}
            ],
            'parts': [
                {{'part_number': 'PART_001', 'name': 'Sample Part 1', 'price': 100}},
                {{'part_number': 'PART_002', 'name': 'Sample Part 2', 'price': 200}}
            ],
            'warranty': [
                {{'vin': 'VIN_001', 'warranty_status': 'Active', 'expiry_date': '2025-12-31'}},
                {{'vin': 'VIN_002', 'warranty_status': 'Expired', 'expiry_date': '2023-12-31'}}
            ],
            'appointment': [
                {{'appointment_id': 'APPT_001', 'dealer_id': 'DEALER_001', 'date': '2024-01-15'}},
                {{'appointment_id': 'APPT_002', 'dealer_id': 'DEALER_002', 'date': '2024-01-16'}}
            ]
        }}
        
        # Populate each table
        for table_type, table_name in table_names.items():
            if table_name and table_type in sample_data:
                table = dynamodb.Table(table_name)
                for item in sample_data[table_type]:
                    table.put_item(Item=item)
                    print(f"Inserted item into {{table_name}}: {{item}}")
        
        return True
    
    except Exception as e:
        print(f"Error populating sample data: {{e}}")
        return False
'''

    def _get_dealer_data_code(self) -> str:
        """Get dealer data function code"""
        return '''
import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')

def get_dealer_data(event, context):
    """Get dealer information"""
    try:
        table_name = os.environ.get('DEALER_DATA_TABLE')
        if not table_name:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'DEALER_DATA_TABLE environment variable not set'})
            }
        
        table = dynamodb.Table(table_name)
        
        # Extract dealer_id from event
        dealer_id = event.get('dealer_id')
        if not dealer_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'dealer_id is required'})
            }
        
        response = table.get_item(Key={'dealer_id': dealer_id})
        
        if 'Item' in response:
            return {
                'statusCode': 200,
                'body': json.dumps(response['Item'])
            }
        else:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Dealer not found'})
            }
    
    except Exception as e:
        print(f"Error in get_dealer_data: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

handler = get_dealer_data
'''

    def _get_parts_code(self) -> str:
        """Get parts data function code"""
        return '''
import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')

def get_parts_for_dtc(event, context):
    """Get parts information for DTC codes"""
    try:
        table_name = os.environ.get('PARTS_DATA_TABLE')
        if not table_name:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'PARTS_DATA_TABLE environment variable not set'})
            }
        
        table = dynamodb.Table(table_name)
        
        # Extract part_number from event
        part_number = event.get('part_number')
        if not part_number:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'part_number is required'})
            }
        
        response = table.get_item(Key={'part_number': part_number})
        
        if 'Item' in response:
            return {
                'statusCode': 200,
                'body': json.dumps(response['Item'])
            }
        else:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Part not found'})
            }
    
    except Exception as e:
        print(f"Error in get_parts_for_dtc: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

handler = get_parts_for_dtc
'''

    def _get_warranty_code(self) -> str:
        """Get warranty data function code"""
        return '''
import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')

def get_warranty_data(event, context):
    """Get warranty information"""
    try:
        table_name = os.environ.get('WARRANTY_DATA_TABLE')
        if not table_name:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'WARRANTY_DATA_TABLE environment variable not set'})
            }
        
        table = dynamodb.Table(table_name)
        
        # Extract VIN from event
        vin = event.get('vin')
        if not vin:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'vin is required'})
            }
        
        response = table.get_item(Key={'vin': vin})
        
        if 'Item' in response:
            return {
                'statusCode': 200,
                'body': json.dumps(response['Item'])
            }
        else:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Warranty information not found'})
            }
    
    except Exception as e:
        print(f"Error in get_warranty_data: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

handler = get_warranty_data
'''

    def _get_appointment_code(self) -> str:
        """Get appointment booking function code"""
        return '''
import json
import boto3
import os
import uuid
from datetime import datetime

dynamodb = boto3.resource('dynamodb')

def book_appointment(event, context):
    """Book an appointment"""
    try:
        table_name = os.environ.get('APPOINTMENT_DATA_TABLE')
        if not table_name:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'APPOINTMENT_DATA_TABLE environment variable not set'})
            }
        
        table = dynamodb.Table(table_name)
        
        # Generate appointment ID
        appointment_id = str(uuid.uuid4())
        
        # Create appointment record
        appointment = {
            'appointment_id': appointment_id,
            'dealer_id': event.get('dealer_id'),
            'customer_name': event.get('customer_name'),
            'appointment_date': event.get('appointment_date'),
            'service_type': event.get('service_type'),
            'created_at': datetime.utcnow().isoformat()
        }
        
        table.put_item(Item=appointment)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'appointment_id': appointment_id,
                'message': 'Appointment booked successfully'
            })
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

handler = book_appointment
'''

    def _get_appointment_slots_code(self) -> str:
        """Get appointment slots function code"""
        return '''
import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')

def get_appointment_slots(event, context):
    """Get available appointment slots"""
    try:
        table_name = os.environ.get('APPOINTMENT_DATA_TABLE')
        if not table_name:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'APPOINTMENT_DATA_TABLE environment variable not set'})
            }
        
        # Return mock available slots
        available_slots = [
            {'date': '2024-01-15', 'time': '09:00', 'available': True},
            {'date': '2024-01-15', 'time': '10:00', 'available': True},
            {'date': '2024-01-15', 'time': '11:00', 'available': False},
            {'date': '2024-01-16', 'time': '09:00', 'available': True},
            {'date': '2024-01-16', 'time': '10:00', 'available': True}
        ]
        
        return {
            'statusCode': 200,
            'body': json.dumps({'slots': available_slots})
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

handler = get_appointment_slots
'''

    def _apply_tags(self) -> None:
        """Apply consistent tags to all Lambda functions"""
        for function in self.business_functions.values():
            Tags.of(function).add("Project", "ma3t-agent-toolkit")
            Tags.of(function).add("FunctionType", "Business")
        
        for function in self.data_functions.values():
            Tags.of(function).add("Project", "ma3t-agent-toolkit")
            Tags.of(function).add("FunctionType", "DataPopulation")

    def get_function(self, function_name: str) -> Optional[lambda_.Function]:
        """Get a specific Lambda function by name"""
        return (self.business_functions.get(function_name) or 
                self.data_functions.get(function_name))

    def get_all_functions(self) -> Dict[str, lambda_.Function]:
        """Get all Lambda functions"""
        all_functions = {}
        all_functions.update(self.business_functions)
        all_functions.update(self.data_functions)
        return all_functions

    def get_business_function_names(self) -> list:
        """Get list of business function names"""
        return list(self.business_functions.keys())

    def get_data_function_names(self) -> list:
        """Get list of data function names"""
        return list(self.data_functions.keys())