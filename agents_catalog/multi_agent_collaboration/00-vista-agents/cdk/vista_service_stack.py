"""
Main CDK Stack for Vehicle Service Management System
Implements Multi-Agent Collaboration with Supervisor Routing
"""

import aws_cdk as cdk
from datetime import datetime
from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_s3 as s3,
    Duration,
    RemovalPolicy,
    CustomResource,
)
from constructs import Construct
import json
from bedrock_constructs import MultiAgentSupervisor, SpecialistAgent, ActionGroup
from template_loader import load_lambda_templates
from lambda_mapping_config import LAMBDA_FUNCTION_MAPPING, get_actual_function_name, should_create_fallback

# Default model for all agents
DEFAULT_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

class VistaServiceStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, foundation_model: str = None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # CloudFormation Parameters (no hardcoded values)
        bedrock_model_param = cdk.CfnParameter(
            self, "BedrockModelId",
            type="String",
            default="anthropic.claude-3-haiku-20240307-v1:0",
            description="The Bedrock model ID to use for the agents"
        )
        
        s3_bucket_param = cdk.CfnParameter(
            self, "S3BucketName",
            type="String",
            description="Name of the S3 bucket for resources"
        )
        
        agent_role_param = cdk.CfnParameter(
            self, "AgentRoleArn",
            type="String",
            description="ARN of the IAM role for agents"
        )
        
        # Use parameters instead of hardcoded values
        self.foundation_model = foundation_model or bedrock_model_param.value_as_string
        print(f"Using foundation model: {self.foundation_model}")
        
        # Load templates from lambda-layer directory
        print("Loading Lambda templates from lambda-layer directory...")
        self.template_data = load_lambda_templates()
        
        # Print template summary for debugging
        print("Template summary:")
        for template_name, counts in self.template_data.get('summary', {}).items():
            print(f"  {template_name}: {counts}")
        
        # Use existing S3 bucket instead of creating new one
        self.resource_bucket = s3.Bucket.from_bucket_name(
            self, "VistaResourceBucket",
            bucket_name=s3_bucket_param.value_as_string
        )
        
        # Create DynamoDB tables from templates
        self.create_dynamodb_tables_from_templates()
        
        # Create Lambda functions from templates
        self.create_lambda_functions_from_templates()
        
        # Create sample data functions and populate data
        self.create_sample_data_functions()
        
        # Create Bedrock agent role
        self.create_bedrock_agent_role()
        
        # Create specialist agents
        self.create_specialist_agents()
        
        # Create supervisor agent with collaboration
        self.create_supervisor_agent()
        
        # Create outputs
        self.create_outputs()

    def create_bedrock_agent_role(self):
        """Create IAM role for Bedrock agents"""
        self.bedrock_agent_role = iam.Role(
            self, "BedrockAgentRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com")
        )
        
        # Add comprehensive permissions for Bedrock agent
        self.bedrock_agent_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
                "bedrock:GetFoundationModel",
                "bedrock:ListFoundationModels",
                "bedrock:InvokeAgent",
                "bedrock:GetAgent",
                "bedrock:ListAgents",
                "bedrock:CreateAgent",
                "bedrock:UpdateAgent",
                "bedrock:DeleteAgent",
                "bedrock:GetAgentAlias",
                "bedrock:CreateAgentAlias",
                "bedrock:UpdateAgentAlias",
                "bedrock:DeleteAgentAlias",
                "bedrock:ListAgentAliases",
                "bedrock:GetAgentActionGroup",
                "bedrock:CreateAgentActionGroup",
                "bedrock:UpdateAgentActionGroup",
                "bedrock:DeleteAgentActionGroup",
                "bedrock:ListAgentActionGroups",
                "bedrock:PrepareAgent",
                "bedrock:GetIngestionJob",
                "bedrock:StartIngestionJob",
                "bedrock:ListIngestionJobs",
                "bedrock:AssociateAgentKnowledgeBase",
                "bedrock:DisassociateAgentKnowledgeBase",
                "bedrock:GetAgentKnowledgeBase",
                "bedrock:ListAgentKnowledgeBases",
                "bedrock:UpdateAgentKnowledgeBase"
            ],
            resources=["*"]
        ))
        
        # Add permissions for Lambda invocation
        self.bedrock_agent_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["lambda:InvokeFunction"],
            resources=["*"]  # Will be refined after Lambda functions are created
        ))

    def create_dynamodb_tables_from_templates(self):
        """Create DynamoDB tables from loaded templates"""
        self.tables = {}
        
        template_tables = self.template_data.get('dynamodb_tables', {})
        print(f"Found {len(template_tables)} DynamoDB tables in templates")
        
        for table_name, table_config in template_tables.items():
            properties = table_config.get('properties', {})
            
            # Extract key schema
            key_schema = properties.get('KeySchema', [])
            attribute_definitions = properties.get('AttributeDefinitions', [])
            
            # Build partition key and sort key
            partition_key = None
            sort_key = None
            
            for key in key_schema:
                key_name = key.get('AttributeName')
                key_type = key.get('KeyType')
                
                # Find the attribute type
                attr_type = None
                for attr in attribute_definitions:
                    if attr.get('AttributeName') == key_name:
                        attr_type_str = attr.get('AttributeType')
                        if attr_type_str == 'S':
                            attr_type = dynamodb.AttributeType.STRING
                        elif attr_type_str == 'N':
                            attr_type = dynamodb.AttributeType.NUMBER
                        elif attr_type_str == 'B':
                            attr_type = dynamodb.AttributeType.BINARY
                        break
                
                if key_type == 'HASH':
                    partition_key = dynamodb.Attribute(name=key_name, type=attr_type)
                elif key_type == 'RANGE':
                    sort_key = dynamodb.Attribute(name=key_name, type=attr_type)
            
            # Create the table
            table_args = {
                "table_name": table_name,
                "partition_key": partition_key,
                "billing_mode": dynamodb.BillingMode.PAY_PER_REQUEST,
                "removal_policy": RemovalPolicy.DESTROY
            }
            
            if sort_key:
                table_args["sort_key"] = sort_key
            
            # Create table with sanitized construct ID
            construct_id = f"{table_name.replace('-', '_').title()}Table"
            table = dynamodb.Table(self, construct_id, **table_args)
            
            self.tables[table_name] = table
            print(f"Created DynamoDB table: {table_name}")
        
        # Set convenient references for backward compatibility
        self.dealer_table = self.tables.get('dealer-data')
        self.obd_table = self.tables.get('obd-data')
        self.parts_table = self.tables.get('dtc-parts-lookup')
        self.warranty_table = self.tables.get('warranty-info')
        self.appointment_table = self.tables.get('dealer-appointment-data')
        self.customer_table = self.tables.get('customer-user-profile')
        self.dealer_parts_stock_table = self.tables.get('dealer-parts-stock')
        self.dealer_parts_order_table = self.tables.get('dealer-parts-order')
        
        print(f"Set table references:")
        print(f"  dealer_table: {self.dealer_table.table_name if self.dealer_table else 'None'}")
        print(f"  parts_table: {self.parts_table.table_name if self.parts_table else 'None'}")
        print(f"  warranty_table: {self.warranty_table.table_name if self.warranty_table else 'None'}")
        print(f"  appointment_table: {self.appointment_table.table_name if self.appointment_table else 'None'}")
        print(f"  customer_table: {self.customer_table.table_name if self.customer_table else 'None'}")

    def create_lambda_functions_from_templates(self):
        """Create Lambda functions from loaded templates"""
        self.lambda_functions = {}
        
        # Common Lambda execution role
        self.lambda_role = iam.Role(
            self, "VistaLambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonDynamoDBFullAccess")
            ]
        )
        
        # Add Bedrock invoke permission to the role
        self.lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["bedrock:InvokeModel", "bedrock:InvokeAgent"],
            resources=["*"]
        ))
        
        template_functions = self.template_data.get('lambda_functions', {})
        print(f"Found {len(template_functions)} Lambda functions in templates")
        
        for function_name, function_config in template_functions.items():
            # Skip ONLY actual data loading/population functions - be very specific
            # These are the exact patterns for data loading functions we want to skip:
            data_loading_functions = [
                'InsertCustomerProfiles',    # Customer data insertion
                'InsertWarrantyInfo',        # Warranty data insertion  
                'dtc-parts-data-loader',     # Parts data loader
                'sample-data',               # Any sample data functions
                'populate-data',             # Any populate data functions
                'data-seeder'                # Any data seeding functions
            ]
            
            # Check if this is a data loading function
            is_data_loading = function_name in data_loading_functions
            
            # Also check for custom resource functions (these are for data population)
            is_custom_resource = (
                function_config.get('type', '').startswith('Custom::') or
                'Custom::' in str(function_config.get('properties', {}))
            )
            
            if is_data_loading or is_custom_resource:
                print(f"Skipping data loading function: {function_name}")
                continue
            
            print(f"Processing business logic function: {function_name}")
            
            # Get function configuration
            properties = function_config.get('properties', {})
            runtime_str = properties.get('Runtime', function_config.get('runtime', 'python3.9'))
            architecture_str = function_config.get('architecture', 'x86_64')
            timeout = properties.get('Timeout', function_config.get('timeout', 300))
            memory_size = properties.get('MemorySize', function_config.get('memory_size', 256))
            code = function_config.get('code', '')
            environment = function_config.get('environment', {})
            
            # Map runtime string to CDK runtime
            runtime_map = {
                'python3.9': lambda_.Runtime.PYTHON_3_9,
                'python3.10': lambda_.Runtime.PYTHON_3_10,
                'python3.11': lambda_.Runtime.PYTHON_3_11,
                'python3.12': lambda_.Runtime.PYTHON_3_12,
                'python3.13': lambda_.Runtime.PYTHON_3_13,
            }
            runtime = runtime_map.get(runtime_str, lambda_.Runtime.PYTHON_3_9)
            
            # Map architecture string to CDK architecture
            if isinstance(properties.get('Architectures'), list) and properties.get('Architectures'):
                architecture_str = properties.get('Architectures')[0]
            architecture = lambda_.Architecture.ARM_64 if architecture_str == 'arm64' else lambda_.Architecture.X86_64
            
            # Determine table name for environment variables
            table_name = None
            if 'dealer' in function_name.lower() and 'appointment' not in function_name.lower():
                table_name = self.dealer_table.table_name if self.dealer_table else 'dealer-data'
            elif 'parts' in function_name.lower():
                if 'stock' in function_name.lower():
                    table_name = self.dealer_parts_stock_table.table_name if self.dealer_parts_stock_table else 'dealer-parts-stock'
                elif 'order' in function_name.lower():
                    table_name = self.dealer_parts_order_table.table_name if self.dealer_parts_order_table else 'dealer-parts-order'
                else:
                    table_name = self.parts_table.table_name if self.parts_table else 'dtc-parts-lookup'
            elif 'warranty' in function_name.lower():
                table_name = self.warranty_table.table_name if self.warranty_table else 'warranty-info'
            elif 'appointment' in function_name.lower() or 'book' in function_name.lower():
                if 'BookAppointmentStar' in function_name:
                    # This function needs both dealer-data and customer-user-profile tables
                    pass  # Will handle environment variables separately
                else:
                    table_name = self.appointment_table.table_name if self.appointment_table else 'dealer-appointment-data'
            
            # Set up environment variables
            env_vars = {}
            if table_name:
                env_vars['TABLE_NAME'] = table_name
            
            # Add any environment variables from template
            env_vars.update(environment.get('Variables', {}))
            
            # Create the Lambda function with unique construct ID for business logic
            construct_id = f"BusinessLogic{function_name.replace('-', '_').title()}Function"
            
            lambda_function = lambda_.Function(
                self, construct_id,
                function_name=function_name,
                runtime=runtime,
                architecture=architecture,
                handler=properties.get('Handler', "index.lambda_handler"),
                code=lambda_.Code.from_inline(code),
                environment=env_vars,
                role=self.lambda_role,
                timeout=Duration.seconds(timeout),
                memory_size=memory_size
            )
            
            # Add Bedrock permission
            bedrock_principal = iam.ServicePrincipal("bedrock.amazonaws.com")
            lambda_function.add_permission(
                f"BedrockInvokePermission{construct_id}",
                principal=bedrock_principal,
                action="lambda:InvokeFunction"
            )
            
            self.lambda_functions[function_name] = lambda_function
            print(f"Created Lambda function: {function_name}")
        
        # Set convenient references for backward compatibility
        self.dealer_lambda = self.lambda_functions.get('get-dealer-data')
        self.parts_lambda = self.lambda_functions.get('get-parts-for-dtc')
        self.warranty_lambda = self.lambda_functions.get('GetWarrantyData')
        self.appointment_lambda = self.lambda_functions.get('BookAppointmentStar')
        self.dealer_appt_lambda = self.lambda_functions.get('get-dealer-appointment-slots')
        self.dealer_stock_lambda = self.lambda_functions.get('get-dealer-stock')
        self.place_order_lambda = self.lambda_functions.get('place-parts-order')
        
        print(f"Set Lambda function references:")
        print(f"  dealer_lambda: {self.dealer_lambda.function_name if self.dealer_lambda else 'None'}")
        print(f"  parts_lambda: {self.parts_lambda.function_name if self.parts_lambda else 'None'}")
        print(f"  warranty_lambda: {self.warranty_lambda.function_name if self.warranty_lambda else 'None'}")
        print(f"  appointment_lambda: {self.appointment_lambda.function_name if self.appointment_lambda else 'None'}")

    def create_sample_data_functions(self):
        """Create sample data population functions from templates"""
        self.sample_data_functions = {}
        
        template_functions = self.template_data.get('sample_data_functions', {})
        print(f"Found {len(template_functions)} sample data functions in templates")
        
        for function_name, function_config in template_functions.items():
            # Get function configuration
            properties = function_config.get('properties', {})
            runtime_str = properties.get('Runtime', 'python3.9')
            timeout = properties.get('Timeout', 60)
            memory_size = properties.get('MemorySize', 256)
            code = function_config.get('code', '')
            
            # Map runtime string to CDK runtime
            runtime_map = {
                'python3.9': lambda_.Runtime.PYTHON_3_9,
                'python3.10': lambda_.Runtime.PYTHON_3_10,
                'python3.11': lambda_.Runtime.PYTHON_3_11,
                'python3.12': lambda_.Runtime.PYTHON_3_12,
                'python3.13': lambda_.Runtime.PYTHON_3_13,
            }
            runtime = runtime_map.get(runtime_str, lambda_.Runtime.PYTHON_3_9)
            
            # Create IAM role for sample data function
            data_role = iam.Role(
                self, f"{function_name.replace('-', '_').title()}Role",
                assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
                ]
            )
            
            # Add DynamoDB permissions
            data_role.add_to_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:PutItem", "dynamodb:BatchWriteItem"],
                resources=[table.table_arn for table in self.tables.values()]
            ))
            
            # Create the Lambda function with unique construct ID for data loading
            construct_id = f"DataLoader{function_name.replace('-', '_').title()}Function"
            
            sample_function = lambda_.Function(
                self, construct_id,
                function_name=f"data-loader-{function_name}",  # Make data loader function names unique
                runtime=runtime,
                handler=properties.get('Handler', "index.handler"),
                code=lambda_.Code.from_inline(code),
                role=data_role,
                timeout=Duration.seconds(timeout),
                memory_size=memory_size
            )
            
            self.sample_data_functions[function_name] = sample_function
            print(f"Created sample data function: {function_name}")
        
        # Create custom resources from templates
        custom_resources = self.template_data.get('custom_resources', {})
        print(f"Found {len(custom_resources)} custom resources in templates")
        
        # Create a mapping of custom resources to their corresponding data loader functions
        resource_function_mapping = {
            'PopulateData': 'SampleDataFunction',
            'PopulateCustomerData': 'InsertCustomerProfiles', 
            'DataLoaderTrigger': 'dtc-parts-data-loader',
            'PopulateWarrantyData': 'InsertWarrantyInfo'
        }
        
        for resource_name, resource_config in custom_resources.items():
            # Use the explicit mapping to find the correct function
            function_name = resource_function_mapping.get(resource_name)
            
            if function_name and function_name in self.sample_data_functions:
                # Create custom resource to trigger the function
                CustomResource(
                    self, f"{resource_name.replace('-', '_').title()}Trigger",
                    service_token=self.sample_data_functions[function_name].function_arn
                )
                print(f"Created custom resource: {resource_name} -> {function_name}")
            else:
                print(f"Warning: Could not find function for custom resource: {resource_name}")
                if function_name:
                    print(f"  Expected function: {function_name}")
                    print(f"  Available functions: {list(self.sample_data_functions.keys())}")

    def create_specialist_agents(self):
        """Create specialist agents using exact names and models from JSON"""
        self.specialist_agents = {}
        
        # 1. SAM-agent-analyze_vehiclesymptom (Knowledge Base agent)
        self.specialist_agents['vehiclesymptom'] = SpecialistAgent(
            self, "VehicleSymptomSpecialist",
            agent_name="SAM-agent-analyze_vehiclesymptom",
            agent_description="Analyze vehicle symptom and recommend an action / next steps based on severity",
            agent_instruction="As an agent analyze the following vehicle symptom issue by reviewing vehicle manuals, recall data\nPlease provide:\n1. Potential issues\n2. Recommended diagnostic steps\n3. Possible parts that might need replacement\n4. Estimated severity (low/medium/high)\nSummarize a detailed response in 200 words with possible next steps to address it.",
            foundation_model=self.foundation_model,
            agent_resource_role_arn=self.bedrock_agent_role.role_arn,
            action_groups=[]
        )
        self.specialist_agents['vehiclesymptom'].create_alias("analyze-vehiclesymptom-alias")

        # 2. SAM-agent-find-nearestdealership
        dealer_action_config = {
            "action_group_name": "action_group_findnearestdealership",
            "description": "Find nearest dealership based on city details",
            "function_schema": {
                "functions": [
                    {
                        "name": "function-getdealerdata",
                        "description": "Invoke dealerdata function by passing input parameters",
                        "parameters": {
                            "city": {
                                "description": "name of the city",
                                "required": False,
                                "type": "string"
                            }
                        }
                    }
                ]
            }
        }

        dealer_action_groups = []
        if self.dealer_lambda:
            dealer_action_groups = [ActionGroup.from_config(dealer_action_config, self.dealer_lambda)]

        self.specialist_agents['nearestdealership'] = SpecialistAgent(
            self, "FindNearestDealershipSpecialist",  
            agent_name="SAM-agent-find-nearestdealership",
            agent_description="Find nearest automotive dealership",
            agent_instruction="As an agent find nearest automotive dealership based on city. As part of response return dealer name and details",
            foundation_model=self.foundation_model,
            agent_resource_role_arn=self.bedrock_agent_role.role_arn,
            action_groups=dealer_action_groups
        )
        self.specialist_agents['nearestdealership'].create_alias("find-nearestdealership-alias")

        # 3. SAM-agent-bookdealerappt
        appointment_action_config = {
            "action_group_name": "action_group_dealerappt-starformat",
            "description": "This agent helps to book an appointment with an dealership.",
            "function_schema": {
                "functions": [
                    {
                        "name": "action-dealerapptfunction",
                        "description": "Book appt with dealership",
                        "parameters": {
                            "appointment_time": {
                                "description": "appointment time",
                                "required": False,
                                "type": "string"
                            },
                            "dealer_name": {
                                "description": "dealer name", 
                                "required": False,
                                "type": "string"
                            },
                            "appointment_date": {
                                "description": "appointment date",
                                "required": False,
                                "type": "string"
                            },
                            "customer_code": {
                                "description": "customer code",
                                "required": False,
                                "type": "string"
                            }
                        }
                    }
                ]
            }
        }

        bookdealerappt_action_groups = []
        if self.lambda_functions.get('BookAppointmentStar'):
            bookdealerappt_action_groups = [ActionGroup.from_config(appointment_action_config, self.lambda_functions['BookAppointmentStar'])]

        self.specialist_agents['bookdealerappt'] = SpecialistAgent(
            self, "BookDealerApptSpecialist",
            agent_name="SAM-agent-bookdealerappt",
            agent_description="Customer books appointment with the selected dealership to analyze vehicle symptom",
            agent_instruction="This agent helps to book an appointment with an dealership. First extract the dealer code, customer code, appointment date and appointment time from the prompt and invoke the action. Based on appointment availability it return back a star compliant schema with additional data points back as part of response.",
            foundation_model=self.foundation_model,
            agent_resource_role_arn=self.bedrock_agent_role.role_arn,
            action_groups=bookdealerappt_action_groups
        )
        self.specialist_agents['bookdealerappt'].create_alias("bookdealerappt-alias")

        # 4. SAM-agent-finddealeravailability  
        dealeravailability_action_config = {
            "action_group_name": "action_group_finddealerslots",
            "description": "find dealer appointment slots by invoking the lambda function",
            "function_schema": {
                "functions": [
                    {
                        "name": "action_groupfunc_finddealerslots",
                        "description": "Find available appointment slots for a dealer. Input dealer name (required), appointment date (optional in YYYY-MM-DD format, e.g., 2025-06-18 for June 18, 2025)",
                        "parameters": {
                            "dealer_name": {
                                "description": "Name of the dealer/dealership (required)",
                                "required": True,
                                "type": "string"
                            },
                            "appointment_date": {
                                "description": "Appointment date in YYYY-MM-DD format (optional). For June 18, 2025 use '2025-06-18'. If not provided, shows next available slots.",
                                "required": False,
                                "type": "string"
                            }
                        }
                    }
                ]
            }
        }

        dealeravailability_action_groups = []
        if self.lambda_functions.get('get-dealer-appointment-slots'):
            dealeravailability_action_groups = [ActionGroup.from_config(dealeravailability_action_config, self.lambda_functions['get-dealer-appointment-slots'])]

        self.specialist_agents['finddealeravailability'] = SpecialistAgent(
            self, "FindDealerAvailabilitySpecialist",
            agent_name="SAM-agent-finddealeravailability",
            agent_description="Find dealership availability that will help customer to book appt",
            agent_instruction=f"""As an agent, check available appointment slots for customers to book appointments to bring their vehicle for analysis. 

IMPORTANT: Today's date is {datetime.now().strftime('%Y-%m-%d')} ({datetime.now().strftime('%B %d, %Y')}). When customers mention dates like "June 18, 2025" or "June 18th", always use the year 2025 or later.

Customer provides:
- Dealer name (required)
- Date (optional) - if not provided, show next available slots starting from tomorrow
- Time (optional)

When processing dates:
- Always interpret relative dates like "June 18" as the next occurrence (2025 or later)
- Use format YYYY-MM-DD when calling the function
- For "June 18, 2025" use "2025-06-18"

Return available appointment slots to help customers select and book appointments.""",
            foundation_model=self.foundation_model,
            agent_resource_role_arn=self.bedrock_agent_role.role_arn,
            action_groups=dealeravailability_action_groups
        )
        self.specialist_agents['finddealeravailability'].create_alias("finddealeravailability-alias")

        # 5. SAM-agent-parts-availability
        parts_action_groups = []
        
        # Multiple action groups for parts agent
        dtc_parts_config = {
            "action_group_name": "action_group_findpartsforDTC",
            "description": "Find DTC to parts mapping",
            "function_schema": {
                "functions": [
                    {
                        "name": "function_dtctoparts",
                        "description": "Find automotive parts for this diagnostic trouble code a.ka. DTC",
                        "parameters": {
                            "dtc_code": {
                                "description": "dtc code",
                                "required": False,
                                "type": "string"
                            }
                        }
                    }
                ]
            }
        }
        
        dealer_stock_config = {
            "action_group_name": "action_group_checkdealerstock", 
            "description": "Check dealer inventory on parts",
            "function_schema": {
                "functions": [
                    {
                        "name": "action_group_dealerstock",
                        "description": "Check dealer inventory for parts availability",
                        "parameters": {
                            "dealer_code": {
                                "description": "Dealer name or code",
                                "required": False,
                                "type": "string"
                            },
                            "part_code": {
                                "description": "Parts code",
                                "required": False,
                                "type": "string"
                            }
                        }
                    }
                ]
            }
        }
        
        order_parts_config = {
            "action_group_name": "action_group_orderparts",
            "description": "Order parts to refill stock",
            "function_schema": {
                "functions": [
                    {
                        "name": "function-orderparts",
                        "description": "Order parts based on parts code and quantity",
                        "parameters": {
                            "dealer_code": {
                                "description": "Dealer name or code",
                                "required": False,
                                "type": "string"
                            },
                            "quantity": {
                                "description": "Quantity",
                                "required": False,
                                "type": "string"
                            },
                            "part_code": {
                                "description": "part code", 
                                "required": False,
                                "type": "string"
                            }
                        }
                    }
                ]
            }
        }

        if self.lambda_functions.get('get-parts-for-dtc'):
            parts_action_groups.append(ActionGroup.from_config(dtc_parts_config, self.lambda_functions['get-parts-for-dtc']))
        if self.lambda_functions.get('get-dealer-stock'):
            parts_action_groups.append(ActionGroup.from_config(dealer_stock_config, self.lambda_functions['get-dealer-stock']))
        if self.lambda_functions.get('place-parts-order'):
            parts_action_groups.append(ActionGroup.from_config(order_parts_config, self.lambda_functions['place-parts-order']))

        self.specialist_agents['parts-availability'] = SpecialistAgent(
            self, "PartsAvailabilitySpecialist",
            agent_name="SAM-agent-parts-availability",
            agent_description="Check for available parts based on DTC",
            agent_instruction="As parts availability agent do the following\na) Find parts for the vehicle DTC\nb) Using the parts information, check the dealership inventory for parts stock availability and show them\nc) In addition, If the inventory is zero place parts order. \nThis will help dealership for fast vehicle turn around to customer once the vehicle is at the dealership",
            foundation_model=self.foundation_model,
            agent_resource_role_arn=self.bedrock_agent_role.role_arn,
            action_groups=parts_action_groups
        )
        self.specialist_agents['parts-availability'].create_alias("parts-availability-alias")

        # 6. SAM-agent-warrantyandrecalls
        warranty_action_config = {
            "action_group_name": "action_group_vehiclewarranty",
            "description": "vehicle warranty function",
            "function_schema": {
                "functions": [
                    {
                        "name": "get-warranty-info",
                        "description": "vehicle warranty function",
                        "parameters": {
                            "VIN": {
                                "description": "vehicle identification number",
                                "required": False,
                                "type": "string"
                            }
                        }
                    }
                ]
            }
        }

        warranty_action_groups = []
        if self.lambda_functions.get('GetWarrantyData'):
            warranty_action_groups = [ActionGroup.from_config(warranty_action_config, self.lambda_functions['GetWarrantyData'])]

        self.specialist_agents['warrantyandrecalls'] = SpecialistAgent(
            self, "WarrantyAndRecallsSpecialist",
            agent_name="SAM-agent-warrantyandrecalls",
            agent_description="Agent on warranties and recalls",
            agent_instruction="As an agent use the action group to find out the warranty information for a vehicle based on VIN.",
            foundation_model=self.foundation_model,
            agent_resource_role_arn=self.bedrock_agent_role.role_arn,
            action_groups=warranty_action_groups
        )
        self.specialist_agents['warrantyandrecalls'].create_alias("warrantyandrecalls-alias")

    def create_supervisor_agent(self):
        """Create supervisor agent with multi-agent collaboration"""
        
        # Create supervisor agent - SAM-agent-orchestrater to match the JSON
        self.supervisor_agent = MultiAgentSupervisor(
            self, "VistaSupervisor",
            agent_name="SAM-agent-orchestrater",
            agent_description="Multiagent service agent orchestration with end to end flow",
            agent_instruction="""You are a vehicle service management assistant with two modes:

1. **Service Mode**: For vehicle-specific queries
 - Invoke appropriate actions
 - Access service databases
 - Schedule appointments

2. **Conversation Mode**: For general queries
 - Respond conversationally without invoking actions
 - Provide friendly greetings
 - Explain capabilities
 - Give general advice

Determine the mode based on the query:
- "Hello" → Conversation Mode
- "Find a dealer" → Service Mode
- "What can you do?" → Conversation Mode
- "Schedule service" → Service Mode

In Conversation Mode, simply respond directly without trying to invoke any actions.

In Service Mode, analyze the following vehicle issue
Please provide:
1. Potential issues
2. Recommended diagnostic steps
3. Estimated severity (low/medium/high)
4. find nearest dealership by city and return both dealer name and code
5. Find dealership availability that will help customer to book appoinment
6. Book appointment based on customer availability
7. Using DTC look up find the automotive part
7) check dealer inventory for availability of parts in their internal database. 
8) If out of stock, order parts now. This will help dealership to stock parts and service customer and deliver vehicle on time with out delay
9) Get customer details
10)Get warranty information for the vehicle""",
            foundation_model=self.foundation_model,
            agent_resource_role_arn=self.bedrock_agent_role.role_arn
        )
        
        # Create alias for supervisor
        self.supervisor_alias = self.supervisor_agent.create_alias("orchestrater-alias")
        
        # Add collaborators to supervisor using the correct agent keys
        # Only add collaborators that exist
        if hasattr(self, 'specialist_agents'):
            if 'vehiclesymptom' in self.specialist_agents:
                self.supervisor_agent.add_collaborator(
                    self.specialist_agents['vehiclesymptom'].alias,
                    "vehicle-symptom-analysis",
                    "Use this agent when customers describe vehicle symptoms or need diagnostic analysis. Route here for symptom analysis and severity assessment."
                )
            
            if 'nearestdealership' in self.specialist_agents:
                self.supervisor_agent.add_collaborator(
                    self.specialist_agents['nearestdealership'].alias,
                    "dealer-lookup",
                    "Use this agent when customers need to find nearby dealerships or dealer information. Route here for dealer searches and location queries."
                )
            
            if 'bookdealerappt' in self.specialist_agents:
                self.supervisor_agent.add_collaborator(
                    self.specialist_agents['bookdealerappt'].alias,
                    "appointment-booking",
                    "Use this agent when customers want to book appointments with dealerships. Route here for appointment scheduling."
                )
            
            if 'finddealeravailability' in self.specialist_agents:
                self.supervisor_agent.add_collaborator(
                    self.specialist_agents['finddealeravailability'].alias,
                    "dealer-availability",
                    "Use this agent when customers need to check dealer availability or appointment slots. Route here for availability checking."
                )
            
            if 'parts-availability' in self.specialist_agents:
                self.supervisor_agent.add_collaborator(
                    self.specialist_agents['parts-availability'].alias,
                    "parts-availability", 
                    "Use this agent when customers need parts information or availability checking. Route here for DTC code lookups and parts ordering."
                )
            
            if 'warrantyandrecalls' in self.specialist_agents:
                self.supervisor_agent.add_collaborator(
                    self.specialist_agents['warrantyandrecalls'].alias,
                    "warranty-recalls",
                    "Use this agent when customers need warranty information or recall checks. Route here for VIN-based warranty queries."
                )
        
        print("Created supervisor agent with multi-agent collaboration")
        
        # Configure the collaboration after all collaborators are added
        self.supervisor_agent.finalize_collaboration()

    def create_outputs(self):
        """Create stack outputs"""
        
        # Lambda function ARNs - only create outputs for functions that exist
        if self.dealer_lambda:
            cdk.CfnOutput(self, "DealerLambdaArn", 
                         value=self.dealer_lambda.function_arn,
                         description="Dealer data Lambda function ARN")
        
        if self.parts_lambda:
            cdk.CfnOutput(self, "PartsLambdaArn",
                         value=self.parts_lambda.function_arn,
                         description="Parts data Lambda function ARN")
        
        if self.warranty_lambda:
            cdk.CfnOutput(self, "WarrantyLambdaArn", 
                         value=self.warranty_lambda.function_arn,
                         description="Warranty data Lambda function ARN")
        
        if self.appointment_lambda:
            cdk.CfnOutput(self, "AppointmentLambdaArn",
                         value=self.appointment_lambda.function_arn,
                         description="Appointment booking Lambda function ARN")
        
        if self.dealer_appt_lambda:
            cdk.CfnOutput(self, "DealerAppointmentLambdaArn",
                         value=self.dealer_appt_lambda.function_arn,
                         description="Dealer appointment data Lambda function ARN")
        
        # DynamoDB table names - only create outputs for tables that exist
        if self.dealer_table:
            cdk.CfnOutput(self, "DealerTableName",
                         value=self.dealer_table.table_name,
                         description="Dealer data DynamoDB table name")
        
        if self.parts_table:
            cdk.CfnOutput(self, "PartsTableName",
                         value=self.parts_table.table_name,
                         description="Parts data DynamoDB table name")
        
        if self.warranty_table:
            cdk.CfnOutput(self, "WarrantyTableName",
                         value=self.warranty_table.table_name,
                         description="Warranty data DynamoDB table name")
        
        if self.appointment_table:
            cdk.CfnOutput(self, "AppointmentTableName",
                         value=self.appointment_table.table_name,
                         description="Appointment data DynamoDB table name")
        
        # S3 bucket
        cdk.CfnOutput(self, "ResourceBucketName",
                     value=self.resource_bucket.bucket_name,
                     description="S3 bucket for resources")
        
        # Supervisor agent outputs
        if hasattr(self, 'supervisor_agent'):
            cdk.CfnOutput(self, "SupervisorAgentId",
                         value=self.supervisor_agent.agent_id,
                         description="Supervisor agent ID")
            
            if hasattr(self, 'supervisor_alias'):
                cdk.CfnOutput(self, "SupervisorAgentAliasId",
                             value=self.supervisor_alias.attr_agent_alias_id,
                             description="Supervisor agent alias ID")
