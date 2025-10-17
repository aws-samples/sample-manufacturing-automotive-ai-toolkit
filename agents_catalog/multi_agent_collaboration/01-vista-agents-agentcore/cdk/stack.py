#!/usr/bin/env python3
"""
CDK Stack for VISTA Agent DynamoDB Tables
Creates and seeds tables for the in-vehicle agentic AI assistant
"""

from aws_cdk import (
    NestedStack,
    Stack,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    RemovalPolicy,
    CfnOutput
)
from aws_cdk.custom_resources import (
    AwsCustomResource,
    AwsCustomResourcePolicy,
    PhysicalResourceId
)
from constructs import Construct

class VistaAgentStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, shared_resources=None, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        # Dealer_Data Table
        self.dealer_data_table = dynamodb.Table(
            self, "DealerDataTable",
            table_name="Dealer_Data",
            partition_key=dynamodb.Attribute(
                name="city",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="dealer_code",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True
        )
        
        # Customer_Data Table
        self.customer_data_table = dynamodb.Table(
            self, "CustomerDataTable",
            table_name="Customer_Data",
            partition_key=dynamodb.Attribute(
                name="CustomerID",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="Model",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True
        )
        
        # Dealer_Appointment_Data Table
        self.dealer_appointment_table = dynamodb.Table(
            self, "DealerAppointmentDataTable",
            table_name="Dealer_Appointment_Data",
            partition_key=dynamodb.Attribute(
                name="dealer_name",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="appointment_date_time",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True
        )
        
        # Strands_Conversation_History Table
        self.conversation_history_table = dynamodb.Table(
            self, "StrandsConversationHistoryTable",
            table_name="Strands_Conversation_History",
            partition_key=dynamodb.Attribute(
                name="session_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True
        )
        
        # Create custom Lambda execution role for seeding operations
        custom_resource_role = iam.Role(
            self, "CustomResourceExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Custom execution role for DynamoDB seeding Lambda functions"
        )
        
        # Add custom policy for Lambda basic execution (instead of AWS managed policy)
        custom_resource_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream", 
                    "logs:PutLogEvents"
                ],
                resources=[f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/lambda/custom-resource-seeder"]
            )
        )
        
        # Add DynamoDB permissions for seeding
        custom_resource_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:PutItem"],
                resources=[
                    self.dealer_data_table.table_arn,
                    self.customer_data_table.table_arn,
                    self.dealer_appointment_table.table_arn
                ]
            )
        )
        
        # Seed Dealer_Data
        dealer_items = [
            {"city": {"S": "Sao Paolo"}, "dealer_code": {"S": "D042"}, "dealer_name": {"S": "Quest Autos"}, "street": {"S": "1730 Embarcadero Rd"}, "state": {"S": "São Paulo"}, "country": {"S": "Brasil"}, "zip": {"S": "94303"}, "phone": {"S": "(650) 555-8765"}, "email": {"S": "info@questautos.com"}, "website": {"S": "https://www.questautos.com"}, "latitude": {"N": "37.442899999999995"}, "longitude": {"N": "-122.144"}},
            {"city": {"S": "Sao Paolo"}, "dealer_code": {"S": "D072"}, "dealer_name": {"S": "Unity Cars"}, "street": {"S": "2500 El Camino Real"}, "state": {"S": "São Paulo"}, "country": {"S": "Brasil"}, "zip": {"S": "94040"}, "phone": {"S": "(650) 555-9876"}, "email": {"S": "sales@unitycars.com"}, "website": {"S": "https://www.unitycars.com"}, "latitude": {"N": "37.3871"}, "longitude": {"N": "-122.0849"}},
            {"city": {"S": "Berlin"}, "dealer_code": {"S": "D011"}, "dealer_name": {"S": "Keen Cars"}, "street": {"S": "Sonnenallee 123"}, "state": {"S": "Berlin"}, "country": {"S": "Germany"}, "zip": {"S": "12045"}, "phone": {"S": "+49 30 555-4321"}, "email": {"S": "contact@keencars.com"}, "website": {"S": "https://www.keencars.com"}, "latitude": {"N": "52.52"}, "longitude": {"N": "13.405"}},
            {"city": {"S": "Berlin"}, "dealer_code": {"S": "D099"}, "dealer_name": {"S": "Area Autos"}, "street": {"S": "Tauentzienstrasse 9-12"}, "state": {"S": "Berlin"}, "country": {"S": "Germany"}, "zip": {"S": "10789"}, "phone": {"S": "+49 30 555-2345"}, "email": {"S": "info@areaautos.com"}, "website": {"S": "https://www.areaautos.com"}, "latitude": {"N": "52.517"}, "longitude": {"N": "13.3888"}},
            {"city": {"S": "Fremont"}, "dealer_code": {"S": "D028"}, "dealer_name": {"S": "Crown Cars"}, "street": {"S": "1302 N First St"}, "state": {"S": "CA"}, "country": {"S": "USA"}, "zip": {"S": "95112"}, "phone": {"S": "(408) 555-7890"}, "email": {"S": "info@crowncars.com"}, "website": {"S": "https://www.crowncars.com"}, "latitude": {"N": "37.3452"}, "longitude": {"N": "-121.89330000000001"}},
            {"city": {"S": "Fremont"}, "dealer_code": {"S": "D037"}, "dealer_name": {"S": "Legend Motors"}, "street": {"S": "2107 Shattuck Ave"}, "state": {"S": "CA"}, "country": {"S": "USA"}, "zip": {"S": "94704"}, "phone": {"S": "(510) 555-1234"}, "email": {"S": "sales@legendmotors.com"}, "website": {"S": "https://www.legendmotors.com"}, "latitude": {"N": "37.8775"}, "longitude": {"N": "-122.279"}},
            {"city": {"S": "Fremont"}, "dealer_code": {"S": "D055"}, "dealer_name": {"S": "Apex Autos"}, "street": {"S": "43191 Mission Blvd"}, "state": {"S": "CA"}, "country": {"S": "USA"}, "zip": {"S": "94539"}, "phone": {"S": "(510) 555-6543"}, "email": {"S": "sales@apexautos.com"}, "website": {"S": "https://www.apexautos.com"}, "latitude": {"N": "37.7749"}, "longitude": {"N": "-122.4194"}}
        ]
        
        for i, item in enumerate(dealer_items):
            AwsCustomResource(
                self, f"SeedDealer{i}",
                on_create={
                    "service": "DynamoDB",
                    "action": "putItem",
                    "parameters": {
                        "TableName": self.dealer_data_table.table_name,
                        "Item": item
                    },
                    "physical_resource_id": PhysicalResourceId.of(f"seed-dealer-{i}")
                },
                policy=AwsCustomResourcePolicy.from_statements([
                    iam.PolicyStatement(
                        actions=["dynamodb:PutItem"],
                        resources=[self.dealer_data_table.table_arn]
                    )
                ]),
                role=custom_resource_role
            )
        
        # Seed Customer_Data
        customer_items = [
            {"CustomerID": {"S": "Remy"}, "Model": {"S": "Astra"}, "Make": {"S": "Fast Motors"}, "ModelYear": {"S": "2024"}, "VehicleID": {"S": "3LNHL2GC7CR830465"}, "ActiveDTCCode": {"S": "U0264"}, "DTCDescription": {"S": "This code means that the Camera Module Rear (CMR) and other control modules on the vehicle\nare not communicating with each other."}, "Severity": {"S": "High"}, "PreferredDealer": {"S": "Apex Autos"}, "email": {"S": "your-email-here@gmail.com"}},
            {"CustomerID": {"S": "JSmith"}, "Model": {"S": "Astra"}, "Make": {"S": "Fast Motors"}, "ModelYear": {"S": "2024"}, "VehicleID": {"S": "3LNHL2GC7CR830464"}, "ActiveDTCCode": {"S": "U0264"}, "DTCDescription": {"S": "This code means that the Camera Module Rear (CMR) and other control modules on the vehicle\nare not communicating with each other."}, "Severity": {"S": "High"}, "PreferredDealer": {"S": "Keen Cars"}, "email": {"S": "your-email-here@gmail.com"}}
        ]
        
        for i, item in enumerate(customer_items):
            AwsCustomResource(
                self, f"SeedCustomer{i}",
                on_create={
                    "service": "DynamoDB",
                    "action": "putItem",
                    "parameters": {
                        "TableName": self.customer_data_table.table_name,
                        "Item": item
                    },
                    "physical_resource_id": PhysicalResourceId.of(f"seed-customer-{i}")
                },
                policy=AwsCustomResourcePolicy.from_statements([
                    iam.PolicyStatement(
                        actions=["dynamodb:PutItem"],
                        resources=[self.customer_data_table.table_arn]
                    )
                ]),
                role=custom_resource_role
            )
        
        # Seed Dealer_Appointment_Data
        appointment_items = [
            {"dealer_name": {"S": "Keen Cars"}, "appointment_date_time": {"S": "2025-09-05 09:00 AM"}, "customer_code": {"S": "CUST001"}, "technician_code": {"S": "TECH001"}},
            {"dealer_name": {"S": "Quest Autos"}, "appointment_date_time": {"S": "2025-09-18 10:00"}, "customer_code": {"S": "JSmith"}, "technician_code": {"S": "TECH001"}}
        ]
        
        for i, item in enumerate(appointment_items):
            AwsCustomResource(
                self, f"SeedAppointment{i}",
                on_create={
                    "service": "DynamoDB",
                    "action": "putItem",
                    "parameters": {
                        "TableName": self.dealer_appointment_table.table_name,
                        "Item": item
                    },
                    "physical_resource_id": PhysicalResourceId.of(f"seed-appointment-{i}")
                },
                policy=AwsCustomResourcePolicy.from_statements([
                    iam.PolicyStatement(
                        actions=["dynamodb:PutItem"],
                        resources=[self.dealer_appointment_table.table_arn]
                    )
                ]),
                role=custom_resource_role
            )
        
        # IAM Role for Agent Execution
        self.agent_execution_role = iam.Role(
            self, "VistaAgentExecutionRole",
            role_name="VistaAgentExecutionRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
                iam.ServicePrincipal("ecs-tasks.amazonaws.com")
            ),
            description="Execution role for VISTA Agent"
        )
        
        # DynamoDB permissions
        dynamodb_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:DeleteItem",
                "dynamodb:Scan",
                "dynamodb:Query"
            ],
            resources=[
                self.dealer_data_table.table_arn,
                self.customer_data_table.table_arn,
                self.dealer_appointment_table.table_arn,
                self.conversation_history_table.table_arn
            ]
        )
        
        # Bedrock permissions - specific to Claude models used
        bedrock_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            resources=[
                f"arn:aws:bedrock:{Stack.of(self).region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
                f"arn:aws:bedrock:{Stack.of(self).region}::foundation-model/us.anthropic.claude-3-5-sonnet-20241022-v2:0"
            ]
        )
        
        # Secrets Manager permissions (for Google Calendar integration) - specific secret name
        secrets_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["secretsmanager:GetSecretValue"],
            resources=[f"arn:aws:secretsmanager:{Stack.of(self).region}:{Stack.of(self).account}:secret:prod/google-calendar-credentials"]
        )
        
        # SES permissions (for email notifications) - specific identity
        ses_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["ses:SendEmail", "ses:SendRawEmail"],
            resources=[f"arn:aws:ses:{Stack.of(self).region}:{Stack.of(self).account}:identity/noreply@example.com"]
        )
        
        # CloudWatch Logs permissions - specific log group for this agent
        logs_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            resources=[f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/bedrock-agentcore/vista-agent"]
        )
        
        # Attach policies
        self.agent_execution_role.add_to_policy(dynamodb_policy)
        self.agent_execution_role.add_to_policy(bedrock_policy)
        self.agent_execution_role.add_to_policy(secrets_policy)
        self.agent_execution_role.add_to_policy(ses_policy)
        self.agent_execution_role.add_to_policy(logs_policy)
        
        # Grant the shared agent role access to our tables
        if shared_resources and 'agent_role' in shared_resources:
            shared_resources['agent_role'].add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "dynamodb:PutItem",
                        "dynamodb:GetItem", 
                        "dynamodb:UpdateItem",
                        "dynamodb:DeleteItem",
                        "dynamodb:Query",
                        "dynamodb:Scan"
                    ],
                    resources=[
                        self.dealer_data_table.table_arn,
                        self.customer_data_table.table_arn,
                        self.dealer_appointment_table.table_arn,
                        self.conversation_history_table.table_arn
                    ]
                )
            )
        
        # Outputs
        CfnOutput(self, "DealerDataTableName", value=self.dealer_data_table.table_name)
        CfnOutput(self, "CustomerDataTableName", value=self.customer_data_table.table_name)
        CfnOutput(self, "DealerAppointmentTableName", value=self.dealer_appointment_table.table_name)
        CfnOutput(self, "ConversationHistoryTableName", value=self.conversation_history_table.table_name)
        CfnOutput(self, "AgentExecutionRoleArn", value=self.agent_execution_role.role_arn)
