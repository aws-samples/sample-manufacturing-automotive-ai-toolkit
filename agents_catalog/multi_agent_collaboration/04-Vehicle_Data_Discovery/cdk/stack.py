"""
CDK Stack for Vehicle Data Discovery
"""

from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
)
from constructs import Construct

class VehicleDataDiscoverySlack(Stack):
    """CDK Stack for Vehicle Data Discovery infrastructure"""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Example DynamoDB table
        self.table = dynamodb.Table(
            self, "AgentTable",
            table_name=f"Vehicle_Data_Discovery-data",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Example Lambda function
        self.lambda_function = _lambda.Function(
            self, "AgentFunction",
            function_name=f"Vehicle_Data_Discovery-function",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=_lambda.Code.from_inline("""
def handler(event, context):
    return {"statusCode": 200, "body": "Hello from Vehicle Data Discovery!"}
            """),
            environment={
                "TABLE_NAME": self.table.table_name
            }
        )
        
        # Grant Lambda permissions to access DynamoDB
        self.table.grant_read_write_data(self.lambda_function)
