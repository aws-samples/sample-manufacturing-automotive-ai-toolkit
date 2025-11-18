from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    RemovalPolicy,
    CustomResource,
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    custom_resources as cr,
)
from constructs import Construct

class MainStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB tables
        self._create_dynamodb_tables()
        
        # Create data loader
        self._create_data_loader()
        
        # Create outputs
        self._create_outputs()

    def _create_dynamodb_tables(self):
        """Create DynamoDB tables for inventory management"""
        
        self.customer_order_table = dynamodb.Table(
            self, "CustomerOrderTable",
            table_name="CustomerOrder",
            partition_key=dynamodb.Attribute(
                name="order_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            table_class=dynamodb.TableClass.STANDARD,
            removal_policy=RemovalPolicy.DESTROY
        )

        self.product_bom_table = dynamodb.Table(
            self, "ProductBOMTable",
            table_name="ProductBOM",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            table_class=dynamodb.TableClass.STANDARD,
            removal_policy=RemovalPolicy.DESTROY
        )

        self.inventory_level_table = dynamodb.Table(
            self, "InventoryLevelTable",
            table_name="InventoryLevel",
            partition_key=dynamodb.Attribute(
                name="inventory_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            table_class=dynamodb.TableClass.STANDARD,
            removal_policy=RemovalPolicy.DESTROY
        )

        self.supplier_info_table = dynamodb.Table(
            self, "SupplierInfoTable",
            table_name="SupplierInfo",
            partition_key=dynamodb.Attribute(
                name="supplier_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            table_class=dynamodb.TableClass.STANDARD,
            removal_policy=RemovalPolicy.DESTROY
        )

        self.transfer_orders_table = dynamodb.Table(
            self, "TransferOrdersTable",
            table_name="TransferOrders",
            partition_key=dynamodb.Attribute(
                name="order_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            table_class=dynamodb.TableClass.STANDARD,
            removal_policy=RemovalPolicy.DESTROY
        )

    def _create_data_loader(self):
        """Create Lambda function to load sample data into DynamoDB tables"""
        
        # Data Loader Lambda Function
        self.data_loader_function = _lambda.Function(
            self, "DataLoaderFunction",
            function_name="MA3T_Data_Loader",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=_lambda.Code.from_inline(self._get_data_loader_code()),
            timeout=Duration.seconds(60),
            description="Loads sample data into MA3T DynamoDB tables"
        )

        # Grant permissions to Lambda function to write to DynamoDB tables
        self.customer_order_table.grant_write_data(self.data_loader_function)
        self.product_bom_table.grant_write_data(self.data_loader_function)
        self.inventory_level_table.grant_write_data(self.data_loader_function)
        self.supplier_info_table.grant_write_data(self.data_loader_function)
        self.transfer_orders_table.grant_write_data(self.data_loader_function)

        # Create a Custom Resource Provider that will invoke the Lambda
        self.data_loader_provider = cr.Provider(
            self, "DataLoaderProvider",
            on_event_handler=self.data_loader_function
        )

        # Create Custom Resource that triggers the Lambda function during deployment
        self.populate_data = CustomResource(
            self, "PopulateData",
            service_token=self.data_loader_provider.service_token,
            properties={
                "TriggerDataLoad": "true",  # This ensures it runs during deployment
            }
        )

        # Ensure tables are created before data loading
        self.populate_data.node.add_dependency(self.customer_order_table)
        self.populate_data.node.add_dependency(self.product_bom_table)
        self.populate_data.node.add_dependency(self.inventory_level_table)
        self.populate_data.node.add_dependency(self.supplier_info_table)
        self.populate_data.node.add_dependency(self.transfer_orders_table)

    def _create_outputs(self):
        """Create CloudFormation outputs"""
        
        CfnOutput(
            self, "CustomerOrderTableName",
            value=self.customer_order_table.table_name,
            description="CustomerOrder table name"
        )

        CfnOutput(
            self, "ProductBOMTableName",
            value=self.product_bom_table.table_name,
            description="ProductBOM table name"
        )

        CfnOutput(
            self, "InventoryLevelTableName",
            value=self.inventory_level_table.table_name,
            description="InventoryLevel table name"
        )

        CfnOutput(
            self, "SupplierInfoTableName",
            value=self.supplier_info_table.table_name,
            description="SupplierInfo table name"
        )

        CfnOutput(
            self, "TransferOrdersTableName",
            value=self.transfer_orders_table.table_name,
            description="TransferOrders table name"
        )

        CfnOutput(
            self, "DataLoaderFunctionArn",
            value=self.data_loader_function.function_arn,
            description="Data Loader Lambda function ARN"
        )

        CfnOutput(
            self, "DataLoaderFunctionName",
            value=self.data_loader_function.function_name,
            description="Data Loader Lambda function name"
        )

        CfnOutput(
            self, "ManualDataLoadCommand",
            value=f"aws lambda invoke --function-name {self.data_loader_function.function_name} --payload '{{}}' response.json",
            description="Command to manually invoke data loader if needed"
        )

    def _get_data_loader_code(self) -> str:
        """Returns the Lambda function code for data loading"""
        return '''
import boto3
import json
import urllib.request
from decimal import Decimal

def handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    
    # Handle CloudFormation Custom Resource events
    response_url = event.get('ResponseURL')
    stack_id = event.get('StackId')
    request_id = event.get('RequestId')
    logical_resource_id = event.get('LogicalResourceId')
    physical_resource_id = event.get('PhysicalResourceId', 'DataLoaderPopulation')
    
    response_body = {
        'Status': 'SUCCESS',
        'PhysicalResourceId': physical_resource_id,
        'StackId': stack_id,
        'RequestId': request_id,
        'LogicalResourceId': logical_resource_id
    }
    
    if event.get('RequestType') == 'Delete':
        print("Delete request - sending success response")
        send_response(response_url, response_body)
        return
    
    try:
        dynamodb = boto3.resource('dynamodb')
        
        # CustomerOrder sample data
        customer_order_table = dynamodb.Table('CustomerOrder')
        customer_orders = [
            {'order_id': 'CO_001', 'customer_id': 'Cosmo Inc', 'order_due_date': 't1', 'order_qty': 22, 'product_id': 'ebike-01', 'ship_from': 'Seattle'},
            {'order_id': 'CO_002', 'customer_id': 'Cosmo Inc', 'order_due_date': 't2', 'order_qty': 22, 'product_id': 'ebike-01', 'ship_from': 'Seattle'},
            {'order_id': 'CO_003', 'customer_id': 'Cosmo Inc', 'order_due_date': 't3', 'order_qty': 28, 'product_id': 'ebike-01', 'ship_from': 'Seattle'},
            {'order_id': 'CO_004', 'customer_id': 'Cosmo Inc', 'order_due_date': 't4', 'order_qty': 29, 'product_id': 'ebike-01', 'ship_from': 'Seattle'},
            {'order_id': 'CO_005', 'customer_id': 'Cosmo Inc', 'order_due_date': 't5', 'order_qty': 35, 'product_id': 'ebike-01', 'ship_from': 'Seattle'},
            {'order_id': 'CO_006', 'customer_id': 'Cosmo Inc', 'order_due_date': 't6', 'order_qty': 32, 'product_id': 'ebike-01', 'ship_from': 'Seattle'},
            {'order_id': 'CO_007', 'customer_id': 'Cosmo Inc', 'order_due_date': 't7', 'order_qty': 38, 'product_id': 'ebike-01', 'ship_from': 'Seattle'}
        ]
        for item in customer_orders:
            customer_order_table.put_item(Item=item)
        print(f"Added {len(customer_orders)} customer orders")
        
        # ProductBOM sample data
        product_bom_table = dynamodb.Table('ProductBOM')
        bom_items = [
            {'id': 'B1', 'product_id': 'ebike_01', 'component_product_id': 'Frame', 'component_quantity_per': 1, 'production_process_id': 'assembly', 'site_id': 'Seattle'},
            {'id': 'B12', 'product_id': 'ebike_01', 'component_product_id': 'Battery', 'component_quantity_per': 1, 'production_process_id': 'assembly', 'site_id': 'Seattle'},
            {'id': 'B11', 'product_id': 'ebike_01', 'component_product_id': 'Wheel', 'component_quantity_per': 2, 'production_process_id': 'assembly', 'site_id': 'Seattle'}
        ]
        for item in bom_items:
            product_bom_table.put_item(Item=item)
        print(f"Added {len(bom_items)} BOM items")
        
        # InventoryLevel sample data
        inventory_table = dynamodb.Table('InventoryLevel')
        inventory_items = [
            {'inventory_id': 'inv_1', 'product_id': 'ebike_01', 'on_hand_inventory': 2, 'site_id': 'Seattle'},
            {'inventory_id': 'inv_2', 'component_id': 'Battery', 'on_hand_inventory': 150, 'site_id': 'Seattle'},
            {'inventory_id': 'inv_3', 'component_id': 'Frame', 'on_hand_inventory': 250, 'site_id': 'Seattle'},
            {'inventory_id': 'inv_4', 'component_id': 'Wheel', 'on_hand_inventory': 500, 'site_id': 'Seattle'},
            {'inventory_id': 'inv_5', 'product_id': 'ebike_01', 'on_hand_inventory': 2, 'site_id': 'LosAngeles'},
            {'inventory_id': 'inv_6', 'product_id': 'ebike_01', 'on_hand_inventory': 2, 'site_id': 'NewYork'},
            {'inventory_id': 'inv_7', 'component_id': 'Battery', 'on_hand_inventory': 85, 'site_id': 'LosAngeles'},
            {'inventory_id': 'inv_8', 'component_id': 'Battery', 'on_hand_inventory': 100, 'site_id': 'NewYork'}
        ]
        for item in inventory_items:
            inventory_table.put_item(Item=item)
        print(f"Added {len(inventory_items)} inventory items")
        
        # SupplierInfo sample data
        supplier_table = dynamodb.Table('SupplierInfo')
        suppliers = [
            {'supplier_id': 'SUP001', 'Supplier_Name': 'Acme Battery Supply Co', 'component_id': 'Battery', 
             'Emissions': 1, 'Lead_time': 1, 'Location': 'Seattle', 'Min_Order_Qty': 50, 'Unit_Price': Decimal('8')},
            {'supplier_id': 'SUP002', 'Supplier_Name': 'PowerCell Industries', 'component_id': 'Battery', 
             'Emissions': 12, 'Lead_time': 4, 'Location': 'Seattle', 'Min_Order_Qty': 50, 'Unit_Price': Decimal('9')},
            {'supplier_id': 'SUP003', 'Supplier_Name': 'TechFrame Manufacturing', 'component_id': 'Battery', 
             'Emissions': 612, 'Lead_time': 4, 'Location': 'New York', 'Min_Order_Qty': 25, 'Unit_Price': Decimal('10')}
        ]
        for item in suppliers:
            supplier_table.put_item(Item=item)
        print(f"Added {len(suppliers)} suppliers")
        
        total_records = len(customer_orders) + len(bom_items) + len(inventory_items) + len(suppliers)
        print(f"Successfully added {total_records} total records across all tables")
        
        response_body['Data'] = {'Message': f"Added {total_records} sample records"}
        send_response(response_url, response_body)
        
        return {
            'statusCode': 200,
            'body': json.dumps(f'Successfully loaded {total_records} records into DynamoDB tables!')
        }
        
    except Exception as e:
        error_message = str(e)
        print(f"Error adding sample data: {error_message}")
        response_body['Status'] = 'FAILED'
        response_body['Reason'] = error_message
        send_response(response_url, response_body)
        
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }

def send_response(response_url, response_body):
    json_response_body = json.dumps(response_body)
    print(f"Sending response to: {response_url}")
    
    headers = {
        'content-type': '',
        'content-length': str(len(json_response_body))
    }
    
    try:
        req = urllib.request.Request(response_url, 
                                    data=json_response_body.encode('utf-8'),
                                    headers=headers,
                                    method='PUT')
        response = urllib.request.urlopen(req)
        print(f"Status code: {response.getcode()}")
        return True
    except Exception as e:
        print(f"Failed to send response: {str(e)}")
        return False
'''
