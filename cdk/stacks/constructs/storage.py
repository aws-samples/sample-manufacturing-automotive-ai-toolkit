"""
Storage Construct for S3 and DynamoDB resources
"""

from aws_cdk import (
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    RemovalPolicy,
    Tags,
    CfnParameter,
)
from cdk_nag import NagSuppressions
from constructs import Construct
from typing import Dict, Optional
import os
import sys

# Template loader is now handled by individual nested stacks
# No hardcoded paths to specific agents
def load_lambda_templates():
    """Fallback template loader - individual stacks should handle their own templates"""
    return {
        'dynamodb_tables': {},
        'lambda_functions': {},
        'sample_data_functions': {},
        'custom_resources': {}
    }


class StorageConstruct(Construct):
    """
    Manages S3 buckets and DynamoDB tables for the MA3T application.
    """

    def __init__(self, scope: Construct, construct_id: str,
                 s3_bucket_name: Optional[str] = None, **kwargs) -> None:
        super().__init__(scope, construct_id)

        # Create S3 bucket
        self._create_s3_bucket(s3_bucket_name)

        # Load template data and create DynamoDB tables
        template_data = load_lambda_templates()
        self._create_dynamodb_tables(template_data.get('dynamodb_tables', {}))

        # Apply tags to all resources
        self._apply_tags()

    def _create_s3_bucket(self, bucket_name: Optional[str] = None) -> None:
        """Create the main S3 bucket for code storage and resources"""
        bucket_props = {
            'block_public_access': s3.BlockPublicAccess.BLOCK_ALL,
            'removal_policy': RemovalPolicy.RETAIN,
            'versioned': False,
            'enforce_ssl': True
        }

        if bucket_name:
            bucket_props['bucket_name'] = bucket_name
        # If no bucket name provided, let CDK generate a unique name

        self.resource_bucket = s3.Bucket(
            self, "ResourceBucket",
            **bucket_props
        )

        # Suppress CDK-Nag rule for S3 access logging (not needed for demo/dev environment)
        NagSuppressions.add_resource_suppressions(
            self.resource_bucket,
            [{"id": "AwsSolutions-S1", "reason": "S3 access logging not required for demo/development environment"}]
        )

    def _create_dynamodb_tables(self, table_definitions: Dict[str, Dict]) -> None:
        """Create DynamoDB tables from template definitions"""
        self.tables: Dict[str, dynamodb.Table] = {}

        # If no table definitions from templates, create default tables
        if not table_definitions:
            self._create_default_tables()
            return

        for table_name, table_def in table_definitions.items():
            properties = table_def.get('properties', {})

            # Extract table configuration
            table_config = {
                'table_name': table_name,
                'removal_policy': RemovalPolicy.DESTROY,
                'billing_mode': self._get_billing_mode(properties),
                'point_in_time_recovery_specification': dynamodb.PointInTimeRecoverySpecification(
                    point_in_time_recovery_enabled=properties.get('PointInTimeRecoverySpecification', {}).get('PointInTimeRecoveryEnabled', False)
                )
            }

            # Add partition key and sort key
            key_schema = properties.get('KeySchema', [])
            attribute_definitions = properties.get('AttributeDefinitions', [])

            if key_schema and attribute_definitions:
                # Find partition key
                partition_key = next((key for key in key_schema if key.get('KeyType') == 'HASH'), None)
                if partition_key:
                    attr_name = partition_key['AttributeName']
                    attr_type = self._get_attribute_type(attribute_definitions, attr_name)
                    table_config['partition_key'] = dynamodb.Attribute(
                        name=attr_name,
                        type=attr_type
                    )

                # Find sort key
                sort_key = next((key for key in key_schema if key.get('KeyType') == 'RANGE'), None)
                if sort_key:
                    attr_name = sort_key['AttributeName']
                    attr_type = self._get_attribute_type(attribute_definitions, attr_name)
                    table_config['sort_key'] = dynamodb.Attribute(
                        name=attr_name,
                        type=attr_type
                    )

            # Create the table
            table = dynamodb.Table(
                self, f"Table{table_name.replace('-', '').replace('_', '')}",
                **table_config
            )

            # Add Global Secondary Indexes if defined
            gsi_definitions = properties.get('GlobalSecondaryIndexes', [])
            for gsi in gsi_definitions:
                gsi_name = gsi.get('IndexName')
                gsi_key_schema = gsi.get('KeySchema', [])

                if gsi_name and gsi_key_schema:
                    # Find GSI partition key
                    gsi_partition_key = next((key for key in gsi_key_schema if key.get('KeyType') == 'HASH'), None)
                    if gsi_partition_key:
                        attr_name = gsi_partition_key['AttributeName']
                        attr_type = self._get_attribute_type(attribute_definitions, attr_name)

                        gsi_config = {
                            'index_name': gsi_name,
                            'partition_key': dynamodb.Attribute(
                                name=attr_name,
                                type=attr_type
                            )
                        }

                        # Find GSI sort key
                        gsi_sort_key = next((key for key in gsi_key_schema if key.get('KeyType') == 'RANGE'), None)
                        if gsi_sort_key:
                            attr_name = gsi_sort_key['AttributeName']
                            attr_type = self._get_attribute_type(attribute_definitions, attr_name)
                            gsi_config['sort_key'] = dynamodb.Attribute(
                                name=attr_name,
                                type=attr_type
                            )

                        table.add_global_secondary_index(**gsi_config)

            self.tables[table_name] = table

    def _create_default_tables(self) -> None:
        """Create default DynamoDB tables if no template definitions are available"""
        default_tables = [
            {
                'name': 'dealer-data',
                'partition_key': dynamodb.Attribute(name='dealer_id', type=dynamodb.AttributeType.STRING)
            },
            {
                'name': 'parts-data',
                'partition_key': dynamodb.Attribute(name='part_number', type=dynamodb.AttributeType.STRING)
            },
            {
                'name': 'warranty-data',
                'partition_key': dynamodb.Attribute(name='vin', type=dynamodb.AttributeType.STRING)
            },
            {
                'name': 'appointment-data',
                'partition_key': dynamodb.Attribute(name='appointment_id', type=dynamodb.AttributeType.STRING)
            }
        ]

        for table_def in default_tables:
            table = dynamodb.Table(
                self, f"Table{table_def['name'].replace('-', '').replace('_', '')}",
                table_name=table_def['name'],
                partition_key=table_def['partition_key'],
                billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                removal_policy=RemovalPolicy.DESTROY,
                point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                    point_in_time_recovery_enabled=False
                )
            )
            self.tables[table_def['name']] = table

    def _get_billing_mode(self, properties: Dict) -> dynamodb.BillingMode:
        """Extract billing mode from table properties"""
        billing_mode = properties.get('BillingMode', 'PAY_PER_REQUEST')
        if billing_mode == 'PROVISIONED':
            return dynamodb.BillingMode.PROVISIONED
        return dynamodb.BillingMode.PAY_PER_REQUEST

    def _get_attribute_type(self, attribute_definitions: list, attr_name: str) -> dynamodb.AttributeType:
        """Get the attribute type for a given attribute name"""
        attr_def = next((attr for attr in attribute_definitions if attr.get('AttributeName') == attr_name), None)
        if attr_def:
            attr_type = attr_def.get('AttributeType', 'S')
            if attr_type == 'N':
                return dynamodb.AttributeType.NUMBER
            elif attr_type == 'B':
                return dynamodb.AttributeType.BINARY
        return dynamodb.AttributeType.STRING

    def _apply_tags(self) -> None:
        """Apply consistent tags to all storage resources"""
        Tags.of(self.resource_bucket).add("Project", "ma3t-agent-toolkit")

        for table in self.tables.values():
            Tags.of(table).add("Project", "ma3t-agent-toolkit")

    @property
    def bucket_name(self) -> str:
        """Returns the S3 bucket name"""
        return self.resource_bucket.bucket_name

    @property
    def bucket_arn(self) -> str:
        """Returns the S3 bucket ARN"""
        return self.resource_bucket.bucket_arn

    def get_table(self, table_name: str) -> Optional[dynamodb.Table]:
        """Get a specific DynamoDB table by name"""
        return self.tables.get(table_name)

    def get_table_names(self) -> list:
        """Get list of all table names"""
        return list(self.tables.keys())

