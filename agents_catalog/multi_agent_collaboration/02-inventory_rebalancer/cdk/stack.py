from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    Stack,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    NestedStack,
)
from aws_cdk.custom_resources import (
    AwsCustomResource,
    AwsCustomResourcePolicy,
    PhysicalResourceId
)
from constructs import Construct
from typing import Dict, Any, Optional

class InventoryOptimizerStack(NestedStack):
    ''' Docstring '''
    def __init__(self, scope: Construct, construct_id: str,
                 shared_resources: Optional[Dict[str, Any]] = None,
                 foundation_model: str = None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._create_dynamodb_tables()
        self._create_data_loader()
        self._create_outputs()

    def _create_dynamodb_tables(self):
        self.customer_order_table = dynamodb.Table(
            self, "CustomerOrderTable",
            table_name="InventoryOptimizerCustomerOrder",
            partition_key=dynamodb.Attribute(
                name="order_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            table_class=dynamodb.TableClass.STANDARD,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True
        )

        self.product_bom_table = dynamodb.Table(
            self, "ProductBOMTable",
            table_name="InventoryOptimizerProductBOM",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            table_class=dynamodb.TableClass.STANDARD,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True
        )

        self.inventory_level_table = dynamodb.Table(
            self, "InventoryLevelTable",
            table_name="InventoryOptimizerInventoryLevel",
            partition_key=dynamodb.Attribute(
                name="inventory_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            table_class=dynamodb.TableClass.STANDARD,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True
        )

        self.supplier_info_table = dynamodb.Table(
            self, "SupplierInfoTable",
            table_name="InventoryOptimizerSupplierInfo",
            partition_key=dynamodb.Attribute(
                name="supplier_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            table_class=dynamodb.TableClass.STANDARD,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True
        )

        self.transfer_orders_table = dynamodb.Table(
            self, "TransferOrdersTable",
            table_name="InventoryOptimizerTransferOrders",
            partition_key=dynamodb.Attribute(
                name="order_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            table_class=dynamodb.TableClass.STANDARD,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True
        )

    def _create_data_loader(self):
        custom_resource_role = iam.Role(
            self, "CustomResourceExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Custom execution role for DynamoDB seeding"
        )
        
        custom_resource_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream", 
                    "logs:PutLogEvents"
                ],
                resources=[f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/lambda/inventory-data-seeder"]
            )
        )
        
        custom_resource_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:PutItem"],
                resources=[
                    self.customer_order_table.table_arn,
                    self.product_bom_table.table_arn,
                    self.inventory_level_table.table_arn,
                    self.supplier_info_table.table_arn,
                    self.transfer_orders_table.table_arn
                ]
            )
        )
        
        # Customer Orders
        customer_orders = [
            {'order_id': {'S': 'CO_001'}, 'customer_id': {'S': 'Cosmo Inc'}, 'order_due_date': {'S': 't1'}, 'order_qty': {'N': '22'}, 'product_id': {'S': 'ebike-01'}, 'ship_from': {'S': 'Seattle'}},
            {'order_id': {'S': 'CO_002'}, 'customer_id': {'S': 'Cosmo Inc'}, 'order_due_date': {'S': 't2'}, 'order_qty': {'N': '22'}, 'product_id': {'S': 'ebike-01'}, 'ship_from': {'S': 'Seattle'}},
            {'order_id': {'S': 'CO_003'}, 'customer_id': {'S': 'Cosmo Inc'}, 'order_due_date': {'S': 't3'}, 'order_qty': {'N': '28'}, 'product_id': {'S': 'ebike-01'}, 'ship_from': {'S': 'Seattle'}},
            {'order_id': {'S': 'CO_004'}, 'customer_id': {'S': 'Cosmo Inc'}, 'order_due_date': {'S': 't4'}, 'order_qty': {'N': '29'}, 'product_id': {'S': 'ebike-01'}, 'ship_from': {'S': 'Seattle'}},
            {'order_id': {'S': 'CO_005'}, 'customer_id': {'S': 'Cosmo Inc'}, 'order_due_date': {'S': 't5'}, 'order_qty': {'N': '35'}, 'product_id': {'S': 'ebike-01'}, 'ship_from': {'S': 'Seattle'}},
            {'order_id': {'S': 'CO_006'}, 'customer_id': {'S': 'Cosmo Inc'}, 'order_due_date': {'S': 't6'}, 'order_qty': {'N': '32'}, 'product_id': {'S': 'ebike-01'}, 'ship_from': {'S': 'Seattle'}},
            {'order_id': {'S': 'CO_007'}, 'customer_id': {'S': 'Cosmo Inc'}, 'order_due_date': {'S': 't7'}, 'order_qty': {'N': '38'}, 'product_id': {'S': 'ebike-01'}, 'ship_from': {'S': 'Seattle'}}
        ]
        
        for i, item in enumerate(customer_orders):
            AwsCustomResource(
                self, f"SeedCustomerOrder{i}",
                on_create={
                    "service": "DynamoDB",
                    "action": "putItem",
                    "parameters": {
                        "TableName": self.customer_order_table.table_name,
                        "Item": item
                    },
                    "physical_resource_id": PhysicalResourceId.of(f"seed-customer-order-{i}")
                },
                policy=AwsCustomResourcePolicy.from_statements([
                    iam.PolicyStatement(
                        actions=["dynamodb:PutItem"],
                        resources=[self.customer_order_table.table_arn]
                    )
                ]),
                role=custom_resource_role
            )
        
        # Product BOM
        bom_items = [
            {'id': {'S': 'B1'}, 'product_id': {'S': 'ebike_01'}, 'component_product_id': {'S': 'Frame'}, 'component_quantity_per': {'N': '1'}, 'production_process_id': {'S': 'assembly'}, 'site_id': {'S': 'Seattle'}},
            {'id': {'S': 'B12'}, 'product_id': {'S': 'ebike_01'}, 'component_product_id': {'S': 'Battery'}, 'component_quantity_per': {'N': '1'}, 'production_process_id': {'S': 'assembly'}, 'site_id': {'S': 'Seattle'}},
            {'id': {'S': 'B11'}, 'product_id': {'S': 'ebike_01'}, 'component_product_id': {'S': 'Wheel'}, 'component_quantity_per': {'N': '2'}, 'production_process_id': {'S': 'assembly'}, 'site_id': {'S': 'Seattle'}}
        ]
        
        for i, item in enumerate(bom_items):
            AwsCustomResource(
                self, f"SeedBOM{i}",
                on_create={
                    "service": "DynamoDB",
                    "action": "putItem",
                    "parameters": {
                        "TableName": self.product_bom_table.table_name,
                        "Item": item
                    },
                    "physical_resource_id": PhysicalResourceId.of(f"seed-bom-{i}")
                },
                policy=AwsCustomResourcePolicy.from_statements([
                    iam.PolicyStatement(
                        actions=["dynamodb:PutItem"],
                        resources=[self.product_bom_table.table_arn]
                    )
                ]),
                role=custom_resource_role
            )
        
        # Inventory Levels
        inventory_items = [
            {'inventory_id': {'S': 'inv_1'}, 'product_id': {'S': 'ebike_01'}, 'on_hand_inventory': {'N': '2'}, 'site_id': {'S': 'Seattle'}},
            {'inventory_id': {'S': 'inv_2'}, 'component_id': {'S': 'Battery'}, 'on_hand_inventory': {'N': '150'}, 'site_id': {'S': 'Seattle'}},
            {'inventory_id': {'S': 'inv_3'}, 'component_id': {'S': 'Frame'}, 'on_hand_inventory': {'N': '250'}, 'site_id': {'S': 'Seattle'}},
            {'inventory_id': {'S': 'inv_4'}, 'component_id': {'S': 'Wheel'}, 'on_hand_inventory': {'N': '500'}, 'site_id': {'S': 'Seattle'}},
            {'inventory_id': {'S': 'inv_5'}, 'product_id': {'S': 'ebike_01'}, 'on_hand_inventory': {'N': '2'}, 'site_id': {'S': 'LosAngeles'}},
            {'inventory_id': {'S': 'inv_6'}, 'product_id': {'S': 'ebike_01'}, 'on_hand_inventory': {'N': '2'}, 'site_id': {'S': 'NewYork'}},
            {'inventory_id': {'S': 'inv_7'}, 'component_id': {'S': 'Battery'}, 'on_hand_inventory': {'N': '85'}, 'site_id': {'S': 'LosAngeles'}},
            {'inventory_id': {'S': 'inv_8'}, 'component_id': {'S': 'Battery'}, 'on_hand_inventory': {'N': '100'}, 'site_id': {'S': 'NewYork'}}
        ]
        
        for i, item in enumerate(inventory_items):
            AwsCustomResource(
                self, f"SeedInventory{i}",
                on_create={
                    "service": "DynamoDB",
                    "action": "putItem",
                    "parameters": {
                        "TableName": self.inventory_level_table.table_name,
                        "Item": item
                    },
                    "physical_resource_id": PhysicalResourceId.of(f"seed-inventory-{i}")
                },
                policy=AwsCustomResourcePolicy.from_statements([
                    iam.PolicyStatement(
                        actions=["dynamodb:PutItem"],
                        resources=[self.inventory_level_table.table_arn]
                    )
                ]),
                role=custom_resource_role
            )
        
        # Suppliers
        suppliers = [
            {'supplier_id': {'S': 'SUP001'}, 'Supplier_Name': {'S': 'Acme Battery Supply Co'}, 'component_id': {'S': 'Battery'}, 'Emissions': {'N': '1'}, 'Lead_time': {'N': '1'}, 'Location': {'S': 'Seattle'}, 'Min_Order_Qty': {'N': '50'}, 'Unit_Price': {'N': '8'}},
            {'supplier_id': {'S': 'SUP002'}, 'Supplier_Name': {'S': 'PowerCell Industries'}, 'component_id': {'S': 'Battery'}, 'Emissions': {'N': '12'}, 'Lead_time': {'N': '4'}, 'Location': {'S': 'Seattle'}, 'Min_Order_Qty': {'N': '50'}, 'Unit_Price': {'N': '9'}},
            {'supplier_id': {'S': 'SUP003'}, 'Supplier_Name': {'S': 'TechFrame Manufacturing'}, 'component_id': {'S': 'Battery'}, 'Emissions': {'N': '612'}, 'Lead_time': {'N': '4'}, 'Location': {'S': 'New York'}, 'Min_Order_Qty': {'N': '25'}, 'Unit_Price': {'N': '10'}}
        ]
        
        for i, item in enumerate(suppliers):
            AwsCustomResource(
                self, f"SeedSupplier{i}",
                on_create={
                    "service": "DynamoDB",
                    "action": "putItem",
                    "parameters": {
                        "TableName": self.supplier_info_table.table_name,
                        "Item": item
                    },
                    "physical_resource_id": PhysicalResourceId.of(f"seed-supplier-{i}")
                },
                policy=AwsCustomResourcePolicy.from_statements([
                    iam.PolicyStatement(
                        actions=["dynamodb:PutItem"],
                        resources=[self.supplier_info_table.table_arn]
                    )
                ]),
                role=custom_resource_role
            )

    def _create_outputs(self):
        CfnOutput(self, "CustomerOrderTableName", value=self.customer_order_table.table_name)
        CfnOutput(self, "ProductBOMTableName", value=self.product_bom_table.table_name)
        CfnOutput(self, "InventoryLevelTableName", value=self.inventory_level_table.table_name)
        CfnOutput(self, "SupplierInfoTableName", value=self.supplier_info_table.table_name)
        CfnOutput(self, "TransferOrdersTableName", value=self.transfer_orders_table.table_name)

