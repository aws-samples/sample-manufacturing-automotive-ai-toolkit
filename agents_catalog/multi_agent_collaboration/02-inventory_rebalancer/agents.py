import logging
import os
import json
import boto3
from decimal import Decimal
from typing import Any, List
from datetime import datetime
from strands.models import BedrockModel
from strands import Agent
from strands.tools import tool

logger = logging.getLogger(__name__)

REGION = os.environ.get("AWS_REGION", "us-west-2")

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj)
        return super().default(obj)

# Built-in tools for transfer orders
@tool
def list_pending_transfers() -> str:
    """List all pending transfer orders. Call this function with no arguments to retrieve all pending orders. Returns all pending transfer order data including order_id, from_location, to_location, component_id, quantity, status, and created_at."""
    try:
        logger.info("Getting pending transfer orders")
        table = boto3.resource('dynamodb', region_name=REGION).Table('InventoryOptimizerTransferOrders')
        response = table.scan()
        items = response.get('Items', [])
        
        logger.info(f"Found {len(items)} total orders")
        
        # Filter for pending status
        pending_orders = [item for item in items if item.get('status') == 'pending']
        logger.info(f"Found {len(pending_orders)} pending orders")
        
        result = {
            "pending_orders": pending_orders,
            "total_orders": len(pending_orders)
        }
        
        return json.dumps(result, cls=DecimalEncoder)
        
    except Exception as e:
        logger.error(f"Error in list_pending_transfers: {str(e)}")
        return json.dumps({"error": str(e)})

@tool
def create_transfer_order(from_location: str, component_id: str, quantity: int) -> str:
    """Create a new transfer order to Seattle. Creates a transfer order with status 'pending'."""
    try:
        logger.info(f"Placing transfer order - from: {from_location}, component: {component_id}, quantity: {quantity}")
        
        if not all([from_location, component_id, quantity]):
            error_msg = 'Missing required parameters: from_location, component_id, quantity'
            logger.error(error_msg)
            return json.dumps({"error": error_msg})
        
        table = boto3.resource('dynamodb', region_name=REGION).Table('InventoryOptimizerTransferOrders')
        order_id = f"TO-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        item = {
            'order_id': order_id,
            'from_location': from_location,
            'to_location': 'seattle',
            'component_id': component_id,
            'quantity': int(quantity),
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat()
        }
        
        table.put_item(Item=item)
        logger.info(f"Created transfer order: {order_id}")
        
        result = {
            "message": "Transfer order placed successfully",
            "order": item
        }
        
        return json.dumps(result, cls=DecimalEncoder)
        
    except Exception as e:
        logger.error(f"Error in create_transfer_order: {str(e)}")
        return json.dumps({"error": str(e)})

# Other embedded tools
@tool
def get_production_schedule(days_ahead: int = 7) -> str:
    """Get production schedule from CustomerOrder DynamoDB table"""
    try:
        table = boto3.resource('dynamodb', region_name=REGION).Table('InventoryOptimizerCustomerOrder')
        orders = table.scan().get('Items', [])
        
        schedule = {}
        product_id = None
        
        for order in orders:
            due_date = order.get('order_due_date', '')
            quantity = int(order.get('order_qty', 0)) if isinstance(order.get('order_qty'), Decimal) else order.get('order_qty', 0)
            
            if not product_id:
                product_id = order.get('product_id', 'EBIKE-001')
            
            if due_date:
                schedule[due_date] = schedule.get(due_date, 0) + quantity
        
        sorted_schedule = {day: schedule[day] for day in ['t1', 't2', 't3', 't4', 't5', 't6', 't7'] if day in schedule}
        
        return json.dumps({
            "production_schedule": sorted_schedule,
            "product_id": product_id,
            "total_units": sum(sorted_schedule.values())
        }, cls=DecimalEncoder)
        
    except Exception as e:
        logger.error(f"Error in get_production_schedule: {str(e)}")
        return json.dumps({"error": str(e)})

@tool
def get_supplier_info() -> str:
    """Get supplier information from SupplierInfo DynamoDB table"""
    try:
        table = boto3.resource('dynamodb', region_name=REGION).Table('InventoryOptimizerSupplierInfo')
        response = table.scan()
        items = response.get('Items', [])
        
        suppliers = [{
            "supplier_name": item.get('Supplier_Name', ''),
            "component_id": item.get('component_id', ''),
            "min_order_qty": int(item.get('Min_Order_Qty', 0)) if isinstance(item.get('Min_Order_Qty'), Decimal) else item.get('Min_Order_Qty', 0),
            "emissions": int(item.get('Emissions', 0)) if isinstance(item.get('Emissions'), Decimal) else item.get('Emissions', 0),
            "unit_price": float(item.get('Unit_Price', 0)) if isinstance(item.get('Unit_Price'), Decimal) else item.get('Unit_Price', 0),
            "lead_time": int(item.get('lead_time', 0)) if isinstance(item.get('lead_time'), Decimal) else item.get('lead_time', 0),
            "location": item.get('Location', '')
        } for item in items]
        
        return json.dumps({
            "suppliers": suppliers,
            "total_suppliers": len(suppliers)
        }, cls=DecimalEncoder)
        
    except Exception as e:
        logger.error(f"Error in get_supplier_info: {str(e)}")
        return json.dumps({"error": str(e)})

@tool
def get_inventory_levels() -> str:
    """Get inventory levels from InventoryLevel DynamoDB table"""
    try:
        table = boto3.resource('dynamodb', region_name=REGION).Table('InventoryOptimizerInventoryLevel')
        response = table.scan(
            FilterExpression='component_id > :empty',
            ExpressionAttributeValues={':empty': ' '}
        )
        items = response.get('Items', [])
        
        inventory = [{
            "component_id": item.get('component_id', ''),
            "on_hand_inventory": int(item.get('on_hand_inventory', 0)) if isinstance(item.get('on_hand_inventory'), Decimal) else item.get('on_hand_inventory', 0),
            "site_id": item.get('site_id', '')
        } for item in items]
        
        return json.dumps({
            "inventory_levels": inventory,
            "total_items": len(inventory)
        }, cls=DecimalEncoder)
        
    except Exception as e:
        logger.error(f"Error in get_inventory_levels: {str(e)}")
        return json.dumps({"error": str(e)})

@tool
def get_product_bom(product_id: str = None) -> str:
    """Get bill of materials from ProductBOM DynamoDB table"""
    try:
        table = boto3.resource('dynamodb', region_name=REGION).Table('InventoryOptimizerProductBOM')
        response = table.scan()
        items = response.get('Items', [])
        
        bom_data = []
        for item in items:
            bom_data.append({
                "product_id": item.get('product_id', ''),
                "component_product_id": item.get('component_product_id', ''),
                "component_quantity_per": int(item.get('component_quantity_per', 0)) if isinstance(item.get('component_quantity_per'), Decimal) else item.get('component_quantity_per', 0)
            })
        
        return json.dumps({
            "bom": bom_data,
            "total_components": len(bom_data)
        }, cls=DecimalEncoder)
        
    except Exception as e:
        logger.error(f"Error in get_product_bom: {str(e)}")
        return json.dumps({"error": str(e)})

class AgentOrchestrator:
    
    def _get_system_prompt(self) -> str:
        return """You are an expert Inventory Rebalancing Assistant for an e-bike manufacturer whose manufacturing facility is in Seattle, USA.
        You help analyze production schedules, inventory levels, supplier information, and bill of materials to make informed inventory management 
        and rebalancing decisions. Use the tools available to you to help answer inventory rebalancing questions effectively and professionally.
        
        When considering inventory for Manufacturing, only consider the inventory in Seattle. This is important because the manufacturing 
        facility is only in Seattle. The company has Distribution Centers in New York and Los Angeles. However we need to transfer inventory
        to Seattle for Manufacturing.

        When you are working on a problem to order or secure components use the following response framework: 
        
        1. Consider moving existing inventory from one location to Seattle. Review carbon emissions, lead time and cost for the transfer.
        2. Consider placing an order with a supplier. Review the available suppliers and consider cost, carbon emissions and lead time.
        3. Consider expediting an existing shipment. Assume that expediting shipment will incur extra 10$ per unit and consume 500KG in emissions.
        
        Please analyze all options and present viable options and suggest the best option based on cost, carbon emissions and lead time.
        
        Available Tools:
        - get_production_schedule: Get upcoming production requirements
        - get_product_bom: Get bill of materials for products
        - get_inventory_levels: Check current inventory across facilities
        - get_supplier_info: Get supplier details including pricing, lead times, emissions
        - list_pending_transfers: VIEW/CHECK existing pending transfer orders (NO parameters - just call it to see the list)
        - create_transfer_order: SUBMIT/CREATE a NEW transfer order to Seattle (MUST provide: from_location, component_id, quantity)
        
        IMPORTANT: Use list_pending_transfers to VIEW orders. Use create_transfer_order to CREATE new orders.
        """
    
    def _get_tools(self) -> List[Any]:
        """Get all built-in tools"""
        tools = [
            get_production_schedule,
            get_supplier_info,
            get_inventory_levels,
            get_product_bom,
            list_pending_transfers,
            create_transfer_order
        ]
        
        logger.info(f"Total tools loaded: {len(tools)}")
        logger.info(f"Tool names being passed to agent: {[t.__name__ for t in tools]}")
        return tools
    
    def _get_bedrock_model(self):
        """Get Bedrock model configuration"""
        return BedrockModel(
            model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
            region_name=REGION,
        )
    
    def create_agent(self, jwt_token: str = None) -> Agent:
        """Create the agent using the Strands SDK"""
        return Agent(
            callback_handler=None,
            model=self._get_bedrock_model(),
            system_prompt=self._get_system_prompt(),
            tools=self._get_tools()
        )

def main():
    """Main entry point for the inventory rebalancer agent"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        logger.info("Starting Inventory Rebalancer Agent...")
        
        # Create the agent orchestrator
        orchestrator = AgentOrchestrator()
        agent = orchestrator.create_agent()
        
        logger.info("Agent created successfully")
        logger.info("Agent is ready to process inventory rebalancing requests")
        
        return agent
        
    except Exception as e:
        logger.error(f"Error starting agent: {str(e)}")
        raise

if __name__ == "__main__":
    main()
