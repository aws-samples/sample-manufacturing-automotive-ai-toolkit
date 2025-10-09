from strands import Agent, tool
from strands_tools import http_request
from typing import Dict, Any, List, Optional
import boto3
from botocore.exceptions import ClientError
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional
from dynamodb_json import json_util
from botocore.config import Config as BotocoreConfig
from boto3.dynamodb.conditions import Attr
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.models import BedrockModel

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Set the region from environment variable
#REGION = 'eu-central-1'
REGION = 'eu-central-1'
# Define a system prompt
SYSTEM_PROMPT = """You are a helpful Automotive Service Technician assistant Agent running in a vehicle dealership, responsible for guiding
an automotive technician through the full vehicle service process. You also have capabilities to look at the calendar of
a service technician and also to look up issues in a specific VIN.

You coordinate other specialized agents to collect information, diagnose issues, recommend parts, and record the final service outcome. 
You must always act based on facts and outputs from the sub-agents you call.

If the technician is asking for appointment details then only use the tool get_appointments to get the list of appointments for that technician.

If the technician is asking for recalls information then only use the tool get_vehicle_recalls to get the list of recalls. Just share the open recalls
and do not suggest anything like getting an appointment at a dealership.

If the technician is asking for parts information then only use the tool get_parts_by_dtc to get the list of parts needed to service a DTC code.

If the technician is asking to place a part order then use the tool get_pending_partorder to see if an order is already placed. Use the PartsProductItem as the part code or use the get_parts_by_dtc first to get the part code for the DTC code. If there are no orders then use the place_part_order tool to
place a part order. If there are pending orders then confirm with the technician that there is a pending order and if they want to proceed with placing a new part order. Do not use any other tools for 
placing part orders and do not suggest any other steps.

If the service technician is asking you to help with diagnosing or troubleshooting an issue then use the following instructions:

CRITICAL INSTRUCTION: ONLY answer using information retrieved from the knowledge base and function call outputs. 
DO NOT use your general knowledge about automotive topics. If the knowledge base or the function calls 
don't contain relevant information, inform the customer that you don't have that specific information 
in your database rather than generating an answer from general knowledge.

## Service Process Flow You could Orchestrate

### 1. Intake Phase
- Collect vehicle info: VIN or Customer_ID. The VIN also called as vehicle identification number, is 17 characters long and is alphanumeric.
- If the VIN is provided then use the tool get_customer_vehicles by passing the VIN. Do not query using CustomerID.
- If the CustomerID is provided then use the tool get_customer_vehicles by passing the CustomerID.
- Use the tool get_customer_vehicles to get the current DTC (Diagnostic Trouble Code) and DTC Description.
- Query the Recall Agent to retrieve outstanding and historical recalls for the Make and Model
- Query the Service History Agent for the vehicle's repair records using the VIN

### 2. Diagnosis Phase
- use the DTC code and DTC description retrieved earlier, and use the search_service_manuals tool to detailed instructions to fix an issue.
- Break it into a clear, step-by-step plan
- If multiple causes exist, ask clarifying questions to narrow it down
- If tech requests a deep dive, pull it from the knowledge base

### 3. Completion Phase
Summarize:
- Diagnostics performed
- Final message should include confirmation and maybe a clever sign-off

## Tone Rules
- Use short, punchy sentences
- Use bulleted lists or numbers for steps
- Be clever, energetic, and curious
"""

@tool
def get_service_history(vehicle_id: str) -> str:
    """
    Query the DynamoDB table for complete vehicle service history records.

    Use this tool when you need to retrieve the full maintenance and service history
    for a specific vehicle based on its unique identifier. The query performs an exact
    match on the VehicleID attribute in the Service_History table.

    This tool connects directly to the Service_History DynamoDB table and returns
    all service records associated with the provided vehicle ID, including maintenance dates,
    service types, mileage information, and repair details.

    Convert the vehicle_id to lower case before querying the DynamoDB table.

    Example response:
        [
            {
                "VehicleID": "ABC123",
                "ServiceDate": "2024-03-15",
                "ServiceType": "Regular Maintenance",
                "Mileage": 35000,
                "Description": "Oil change, filter replacement, tire rotation",
                "TechnicianID": "T789",
                "Cost": 149.99,
                "Notes": "Front brake pads replaced and rotors inspected."
            },
            ...
        ]

    Notes:
        - This tool only retrieves historical service records and does not modify any data
        - Results are returned in chronological order by default

    Args:
        vehicle_id: The VehicleID to query
                   Example: "ABC123" or "VIN12345678901234567"

    Returns:
        A JSON string containing all service history records for the specified vehicle,
        or an error message if the query fails or no records are found
    """
    try:
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('Service_History')
        
        print (f"querying the service history table for the VIN {vehicle_id}")
        # Query the table for records matching the vehicle_id
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('VehicleID').eq(vehicle_id.upper())
        )
        
        # Check if any items were returned
        if 'Items' in response and response['Items']:
            # Return the service history records as a formatted JSON string
            print (json.dumps(response['Items'], indent=2))
            return json.dumps(response['Items'], indent=2)
        else:
            print ("No service history found for this vehicle")
            return f"No service history records found for vehicle ID: {vehicle_id}"
            
    except ClientError as e:
        error_message = f"Error querying DynamoDB: {str(e)}"
        logger.error(error_message)
        return error_message
    except Exception as e:
        error_message = f"Unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return error_message

@tool
def get_customer_vehicles(customer_id: str = None, vin: str = None) -> str:
    """
    Retrieve all vehicles owned by a specific customer from the DynamoDB table.
    
    Use this tool when you need to get a list of all vehicles associated
    with a particular customer ID or find a specific vehicle by VIN. The query can use
    either CustomerID (direct query) or VehicleID/VIN (scan with filter)
    
    It returns all vehicle records including make, model, model year, current odometer reading, and vehicle ID.
    
    Example response: (Sample data)
        {
            "CustomerID": "CUST001",
            "Email": "youremail@gmail.com",
            "Vehicles": [
                {
                    "VehicleID": "3LNHL2GC7CR830464",
                    "Make": "Fast Motors",
                    "Model": "Astra",
                    "ModelYear": "2023",
                    "Odometer": 25000,
                    "ActiveDTCCode": "P0240",
                    "DTCDescription":"The OBD-II code P0240 indicates a problem with the Turbocharger/Supercharger Boost Sensor 'B' Circuit. Specifically, the code signifies that the Engine Control Module (ECM) has detected that the sensor's input is outside the acceptable range or is not performing as expected. This can lead to decreased engine performance, including reduced power and potential limp mode."
                }
            ]
        }
    
    Notes:
        - This tool only retrieves customer vehicle information and does not modify any data
    
    Args:
        customer_id: The CustomerID to query (optional if VIN provided)
                    Examples: "CUST001", "CUST123"
        vin: The VIN (Vehicle Identification Number) to query (optional if customer_id provided)
             Examples: "3LNHL2GC7CR830464", "1HGCV1F34NA123456"
    
    Returns:
        A JSON string containing vehicles for the specified customer or VIN,
        or an error message if the query fails or no records are found
    """
    try:
        # Validate input parameters
        if not customer_id and not vin:
            return "Either customer_id or vin must be provided"
        
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('Customer_Data')
        
        if vin:
            # Scan by VIN
            response = table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('VehicleID').eq(vin)
            )
        else:
            # Query by CustomerID (partition key)
            response = table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('CustomerID').eq(customer_id)
            )
        
        # Check if any items were returned
        if 'Items' in response and response['Items']:
            # Format the response
            result = {
                "CustomerID": customer_id if customer_id else response['Items'][0].get('CustomerID', ''),
                "Email": "",
                "Vehicles": []
            }
            
            # Extract vehicle information from the response
            for item in response['Items']:
                # Get email from first record (assuming same for all vehicles)
                if not result["Email"] and 'email' in item:
                    result["Email"] = item['email']
                
                # Build vehicle record with only required fields
                vehicle = {
                    "VehicleID": item.get('VehicleID', ''),
                    "Make": item.get('Make', ''),
                    "Model": item.get('Model', ''),
                    "ModelYear": item.get('ModelYear', ''),
                    "Odometer": item.get('Odometer', 0),
                    "ActiveDTCCode": item.get('ActiveDTCCode', ''),
                    "DTCDescription": item.get('DTCDescription', '')
                }
                
                result['Vehicles'].append(vehicle)
            
            return json.dumps(result, indent=2)
        else:
            search_term = f"VIN: {vin}" if vin else f"customer ID: {customer_id}"
            return f"No vehicles found for {search_term}"
            
    except ClientError as e:
        error_message = f"Error querying DynamoDB: {str(e)}"
        logger.error(error_message)
        return error_message
    except Exception as e:
        error_message = f"Unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return error_message

@tool
def get_vehicle_recalls(model: str = None, year: str = None, vin: str = None) -> str:
    """
    Query the DynamoDB table for vehicle recalls based on model and year OR VIN.
    
    Use this tool when you need to retrieve all safety recalls associated with a specific
    vehicle. You can query either by providing model and year directly, or by providing
    a VIN which will be used to lookup the vehicle details first.
    
    This tool queries the Recalls DynamoDB table and returns all recall records
    associated with the provided vehicle model and year or VIN, including details such as
    affected components, consequences, remedies, and report dates.
    
    Example response:
        {
            "Model": "Camry",
            "Year": "2020",
            "Make": "Toyota",
            "VIN": "1HGCV1F34NA123456",
            "Recalls": [
                {
                    "RecallID": "REC123",
                    "Component": "Brake System",
                    "Consequence": "Increased stopping distance",
                    "Remedy": "Replace brake master cylinder",
                    "ReportDate": "2023-05-15"
                },
                {
                    "RecallID": "REC456",
                    "Component": "Fuel System",
                    "Consequence": "Potential fuel leak and fire hazard",
                    "Remedy": "Replace fuel pump assembly",
                    "ReportDate": "2023-08-22"
                }
            ]
        }
    
    Notes:
        - This tool only retrieves recall information and does not modify any data
        - Results include all recalls issued for the specified model and year
    
    Args:
        model: The vehicle model to query (optional if VIN provided)
               Example: "Camry" or "F-150"
        year: The model year to query (optional if VIN provided)
              Example: "2020" or "2018"
        vin: The Vehicle Identification Number (optional if model/year provided)
             Example: "1HGCV1F34NA123456"
    
    Returns:
        A JSON string containing all recalls for the specified vehicle model and year,
        or an error message if the query fails or no records are found
    """
    try:
        # If VIN is provided, lookup model and year from Service_History table
        if vin:
            # Initialize DynamoDB client for Service_History lookup
            dynamodb = boto3.resource('dynamodb', region_name=REGION)
            service_table = dynamodb.Table('Service_History')
            
            # Query Service_History table with VIN to get model and year
            service_response = service_table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('VehicleID').eq(vin)
            )
            
            if 'Items' in service_response and service_response['Items']:
                # Get model and year from the first service record
                service_record = service_response['Items'][0]
                model = service_record.get('ModelDescription', '')
                year = service_record.get('ModelYear', '')
                
                if not model or not year:
                    return f"Could not find model and year information for VIN: {vin}"
            else:
                return f"No service history found for VIN: {vin}"
        
        # Validate that we have model and year (either provided directly or from VIN lookup)
        if not model or not year:
            return "Either provide model and year, or provide VIN for vehicle lookup"
        
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table('Recalls')
        
        # Query the table for records matching the model and year
        # Note: This assumes a composite key of Model and Year or a GSI
        # If the table structure is different, this query may need adjustment
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('Model').eq(model) & 
                                  boto3.dynamodb.conditions.Key('Year').eq(year)
        )
        
        # Check if any items were returned
        if 'Items' in response and response['Items']:
            # Get the make from the first item (should be consistent for all items)
            make = response['Items'][0].get('Make', '')
            
            # Format the response as expected
            result = {
                "Model": model,
                "Year": year,
                "Make": make,
                "VIN": vin if vin else "Not provided",
                "Recalls": []
            }
            
            # Extract recall information from the response
            for item in response['Items']:
                recall = {
                    "RecallID": item.get('RecallID', ''),
                    "Component": item.get('Component', ''),
                    "Consequence": item.get('Consequence', ''),
                    "Remedy": item.get('Remedy', ''),
                    "ReportDate": item.get('ReportDate', '')
                }
                result['Recalls'].append(recall)
            
            return json.dumps(result, indent=2)
        else:
            return f"No recalls found for {model} {year}"
            
    except ClientError as e:
        error_message = f"Error querying DynamoDB: {str(e)}"
        logger.error(error_message)
        return error_message
    except Exception as e:
        error_message = f"Unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return error_message

@tool
def search_service_manuals(query: str) -> str:
    """
    Search service manuals and technical documentation to assist service technicians with vehicle repairs.
    
    This tool provides access to a comprehensive knowledge base containing service manuals,
    repair procedures, troubleshooting guides, and technical specifications. It uses hybrid
    search combining keyword-based and semantic search capabilities to find the most relevant
    information for vehicle repair and maintenance tasks.
    
    Use this tool when you need to:
    - Find repair procedures for specific vehicle components
    - Get troubleshooting steps for diagnostic codes or symptoms
    - Look up technical specifications or torque values
    - Find part numbers or replacement procedures
    - Get safety precautions for specific repair tasks
    
    The tool searches through service manuals and returns ranked results based on relevance
    to help technicians complete repairs efficiently and safely.
    
    Args:
        query: Search query describing the repair issue, component, or information needed
               Examples: 
               - "brake pad replacement procedure"
               - "engine diagnostic code P0301"
               - "transmission fluid change steps"
               - "alternator removal torque specifications"
    
    Returns:
        A formatted string containing relevant information from service manuals,
        including repair procedures, specifications, and safety notes
    """
    try:
        #kb_id = "3AXZ1EJDHW"  # Your knowledge base ID
        kb_id = "SHRP071A8L"
        bedrock_runtime = boto3.client('bedrock-agent-runtime', region_name=REGION)
        
        # First try with reranking, fallback to basic search if reranking fails
        retrieve_params = {
            "knowledgeBaseId": kb_id,
            "retrievalQuery": {
                "text": query
            },
            "retrievalConfiguration": {
                "vectorSearchConfiguration": {
                    "numberOfResults": 7,
                    "overrideSearchType": "HYBRID"
                }
            }
        }
        
        # Try to add reranking configuration if available
        try:
            retrieve_params["retrievalConfiguration"]["vectorSearchConfiguration"]["rerankingConfiguration"] = {
                'type': 'BEDROCK_RERANKING_MODEL',
                'bedrockRerankingConfiguration': {
                    'modelConfiguration': {
                        'modelArn': 'arn:aws:bedrock:eu-central-1::foundation-model/amazon.rerank-v1:0'
                    },
                    'numberOfRerankedResults': 7
                }
            }
            
            # Execute retrieval with reranking
            response = bedrock_runtime.retrieve(**retrieve_params)
            
        except ClientError as e:
            if "RerankingConfiguration" in str(e):
                logger.info("Reranking not available, falling back to basic hybrid search")
                # Remove reranking configuration and retry
                del retrieve_params["retrievalConfiguration"]["vectorSearchConfiguration"]["rerankingConfiguration"]
                response = bedrock_runtime.retrieve(**retrieve_params)
            else:
                raise e
        
        # Process and format the response
        if 'retrievalResults' in response and response['retrievalResults']:
            formatted_results = []
            for i, result in enumerate(response['retrievalResults'], 1):
                content = result.get('content', {}).get('text', '')
                score = result.get('score', 0)
                
                # Extract source information if available
                source_info = ""
                if 'location' in result:
                    location = result['location']
                    if 's3Location' in location:
                        s3_location = location['s3Location']
                        source_info = f"Source: {s3_location.get('uri', 'Unknown')}"
                
                formatted_results.append(f"Result {i} (Score: {score:.3f}):\n{content}\n{source_info}\n")
            
            return "\n".join(formatted_results)
        else:
            return f"No relevant information found in service manuals for query: {query}"
            
    except ClientError as e:
        error_message = f"Error searching service manuals: {str(e)}"
        logger.error(error_message)
        return error_message
    except Exception as e:
        error_message = f"Unexpected error occurred while searching service manuals: {str(e)}"
        logger.error(error_message)
        return error_message

@tool
def get_parts_by_dtc(dtc_code: str) -> str:
    """
    Query the Parts_to_DTC DynamoDB table to retrieve all parts associated with a specific diagnostic trouble code. Return the PartsProductItem as the part code needed to service the DTC code.
    
    Use this tool when you need to find replacement parts for a specific diagnostic trouble code (DTC).
    This is particularly useful when a technician has diagnosed a vehicle issue and needs to identify
    the correct parts for repair.
    
    The tool connects directly to the Parts_to_DTC DynamoDB table and returns all parts records
    associated with the provided DTC code, including part details, pricing, availability, and supplier information.
    
    Example response:
        {
            "DTC_Code": "P0341",
            "Parts": [
                {
                    "PartsProductItem": "393183L100",
                    "PartSourceCode": "Bosch",
                    "Custom_Discount": 8.9,
                    "Custom_Name": "Camshaft Position Sensor",
                    "Custom_Rating": 4.7,
                    "PartClassCode": "OEM",
                    "PartTypeCode": "P",
                    "QuantityOnHand": 0,
                    "UnitPriceAmount": 33.28
                }
            ]
        }
    
    Args:
        dtc_code: The diagnostic trouble code to query for parts
                 Examples: "P0341", "P0300", "B1234", "C1201"
    
    Returns:
        A JSON string containing all parts associated with the specified DTC code,
        or an error message if the query fails or no parts are found
    """
    try:
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('Parts_to_DTC')
        
        # Query the table for records matching the DTC code
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('DTC_Code').eq(dtc_code.upper())
        )
        
        # Check if any items were returned
        if 'Items' in response and response['Items']:
            # Format the response as expected
            result = {
                "DTC_Code": dtc_code.upper(),
                "Parts": []
            }
            
            # Extract parts information from the response
            for item in response['Items']:
                part = {
                    "PartsProductItem": item.get('PartsProductItem', ''),
                    "PartSourceCode": item.get('PartSourceCode', ''),
                    "Custom_Discount": float(item.get('Custom_Discount', 0)),
                    "Custom_Name": item.get('Custom_Name', ''),
                    "Custom_Rating": float(item.get('Custom_Rating', 0)),
                    "PartClassCode": item.get('PartClassCode', ''),
                    "PartTypeCode": item.get('PartTypeCode', ''),
                    "QuantityOnHand": int(item.get('QuantityOnHand', 0)),
                    "UnitPriceAmount": float(item.get('UnitPriceAmount', 0))
                }
                result['Parts'].append(part)
            
            return json.dumps(result, indent=2)
        else:
            return f"No parts found for DTC code: {dtc_code}"
            
    except ClientError as e:
        error_message = f"Error querying DynamoDB: {str(e)}"
        logger.error(error_message)
        return error_message
    except Exception as e:
        error_message = f"Unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return error_message

@tool
def get_appointments(technician_code: str, date: str = None) -> str:
    """
    Query the Dealer_Appointment_Data DynamoDB table to retrieve appointments for a specific technician.
    
    Use this tool when you need to find appointments scheduled for a technician. The tool can query
    by technician code alone (returns current date and future appointments) or by technician code and specific date.
    
    The tool connects directly to the Dealer_Appointment_Data DynamoDB table and returns all appointment
    records for the specified technician from current date onwards.
    
    Args:
        technician_code: The technician's code to query for appointments
                        Examples: "TECH001", "TECH002", "T123"
        date: Optional date in YYYY-MM-DD format. If provided, filters for that specific date.
              If not provided, returns all appointments from current date onwards.
              Examples: "2025-06-20", "2024-12-15"
    
    Returns:
        A JSON string containing all appointments for the specified technician and date range,
        or an error message if the query fails or no appointments are found
    """
    try:
        from datetime import datetime, timedelta
        
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table('Dealer_Appointment_Data')
        
        # Get current date for filtering
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        print(f"Querying appointments for technician code: {technician_code.upper()}")
        
        # Build filter expression
        filter_expression = Attr('technician_code').eq(technician_code.upper())
        
        if date:
            # Filter for specific date
            filter_expression = filter_expression & Attr('appointment_date_time').begins_with(date)
            print(f"Filtering for specific date: {date}")
        else:
            # Filter for current date and future (appointment_date_time >= current_date)
            filter_expression = filter_expression & Attr('appointment_date_time').gte(current_date)
            print(f"Filtering for current date and future: >= {current_date}")
        
        # Scan the table with filter (since technician_code is not a key)
        response = table.scan(
            FilterExpression=filter_expression
        )
        
        appointments = response.get('Items', [])
        
        # Handle pagination if needed
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression=filter_expression,
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            appointments.extend(response.get('Items', []))
        
        # Format and return results
        if appointments:
            # Sort appointments by appointment_date_time
            appointments.sort(key=lambda x: x.get('appointment_date_time', ''))
            
            result = {
                "technician_code": technician_code,
                "query_date": date if date else f"from {current_date} onwards",
                "appointments": appointments,
                "total_count": len(appointments)
            }
            
            print(f"Found {len(appointments)} appointments")
            return json.dumps(result, indent=2)
        else:
            date_info = f"on {date}" if date else f"from {current_date} onwards"
            message = f"No appointments found for technician {technician_code} {date_info}"
            print(message)
            return message
            
    except ClientError as e:
        error_message = f"Error querying DynamoDB: {str(e)}"
        logger.error(error_message)
        return error_message
    except Exception as e:
        error_message = f"Unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return error_message

@tool
def get_parts_by_name(part_name: str) -> str:
    """
    Query the Parts_to_DTC DynamoDB table to retrieve all parts that match a specific part name.
    
    Use this tool when you need to find parts by their descriptive name rather than DTC code. Examples of part names are
    "Brake Pads", "Camshaft Position Sensor", "Lighting Sensor" etc. Please note that the words are capitalized.
    
    This is particularly useful when a technician knows what part they need but wants to see
    all available options, suppliers, and pricing for that specific part type.
    
    The tool connects directly to the Parts_to_DTC DynamoDB table and performs a scan operation
    to find all parts where the Custom_Name contains the specified search term (case-insensitive).
    
    Example response:
        {
            "Search_Term": "Camshaft Position Sensor",
            "Parts_Found": [
                {
                    "DTC_Code": "P0341",
                    "PartsProductItem": "393183L100",
                    "PartSourceCode": "Bosch",
                    "Custom_Discount": 8.9,
                    "Custom_Name": "Camshaft Position Sensor",
                    "Custom_Rating": 4.7,
                    "PartClassCode": "OEM",
                    "PartTypeCode": "P",
                    "QuantityOnHand": 0,
                    "UnitPriceAmount": 33.28
                },
                {
                    "DTC_Code": "P0340",
                    "PartsProductItem": "3935037110",
                    "PartSourceCode": "Bosch",
                    "Custom_Discount": 9.7,
                    "Custom_Name": "Camshaft Position Sensor",
                    "Custom_Rating": 3.6,
                    "PartClassCode": "OEM",
                    "PartTypeCode": "P",
                    "QuantityOnHand": 5,
                    "UnitPriceAmount": 52.82
                }
            ],
            "Total_Count": 2
        }
    
    Args:
        part_name: The part name or partial name to search for
                  Examples: "Camshaft Position Sensor", "Brake", "Ignition Coil"
    
    Returns:
        A JSON string containing all parts matching the specified name,
        or an error message if the query fails or no parts are found
    """
    try:
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table('Parts_to_DTC')
        
        # Perform scan operation with filter on Custom_Name
        # Note: Using scan because Custom_Name is not a key attribute
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('Custom_Name').contains(part_name)
        )
        
        # Check if any items were returned
        if 'Items' in response and response['Items']:
            # Format the response as expected
            result = {
                "Search_Term": part_name,
                "Parts_Found": [],
                "Total_Count": len(response['Items'])
            }
            
            # Extract parts information from the response
            for item in response['Items']:
                part = {
                    "DTC_Code": item.get('DTC_Code', ''),
                    "PartsProductItem": item.get('PartsProductItem', ''),
                    "PartSourceCode": item.get('PartSourceCode', ''),
                    "Custom_Discount": float(item.get('Custom_Discount', 0)),
                    "Custom_Name": item.get('Custom_Name', ''),
                    "Custom_Rating": float(item.get('Custom_Rating', 0)),
                    "PartClassCode": item.get('PartClassCode', ''),
                    "PartTypeCode": item.get('PartTypeCode', ''),
                    "QuantityOnHand": int(item.get('QuantityOnHand', 0)),
                    "UnitPriceAmount": float(item.get('UnitPriceAmount', 0))
                }
                result['Parts_Found'].append(part)
            
            # Sort parts by Custom_Name for better organization
            result['Parts_Found'].sort(key=lambda x: x.get('Custom_Name', ''))
            
            return json.dumps(result, indent=2)
        else:
            return f"No parts found matching name: {part_name}"
            
    except ClientError as e:
        error_message = f"Error querying DynamoDB: {str(e)}"
        logger.error(error_message)
        return error_message
    except Exception as e:
        error_message = f"Unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return error_message

@tool
def get_pending_partorder(dealer_code: str, part_code: str) -> str:
    """
    Query the Dealer_Parts_Order DynamoDB table to check for pending part orders based on dealer_code and part_code.
    
    Use this tool to check if there is a pending order for a specific part at a dealership and return the quantity.
    The DynamoDB table has only three columns: dealer_code, part_code, and quantity.
    
    Args:
        dealer_code: The dealer code to query
                    Examples: "DLR123", "Jaguar Land Rover Seattle"
        part_code: The part code to query (PartsProductItem)
                  Examples: "393183L100", "3935037110"
    
    Returns:
        A string containing the quantity of pending orders for the specified dealer and part,
        or "0" if no pending orders are found
    """
    try:
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table('Dealer_Parts_Order')
        
        # Query the table for records matching the dealer_code and part_code
        response = table.get_item(
            Key={
                'dealer_code': dealer_code,
                'part_code': part_code
            }
        )
        
        # Check if item was returned
        if 'Item' in response:
            # Return just the quantity
            quantity = response['Item'].get('quantity', 0)
            return str(quantity)
        else:
            return "0"
            
    except ClientError as e:
        error_message = f"Error querying DynamoDB: {str(e)}"
        logger.error(error_message)
        return "0"  # Return 0 on error to allow workflow to continue
    except Exception as e:
        error_message = f"Unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return "0"  # Return 0 on error to allow workflow to continue

@tool
def place_part_order(dealer_code: str, part_code: str) -> str:
    """
    Place an order for a part by either creating a new record or incrementing the quantity of an existing order.
    
    This tool checks if an order for the specified part already exists for the dealer. If it does,
    it increments the quantity by 1. If not, it creates a new order record with quantity 1.
    
    Args:
        dealer_code: The dealer code for the order
                    Examples: "DLR123", "Jaguar Land Rover Seattle"
        part_code: The part code to order (PartsProductItem)
                  Examples: "393183L100", "3935037110"
    
    Returns:
        A string indicating the success or failure of the operation
    """
    try:
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table('Dealer_Parts_Order')
        
        # First check if an order already exists
        response = table.get_item(
            Key={
                'dealer_code': dealer_code,
                'part_code': part_code
            }
        )
        
        if 'Item' in response:
            # Order exists, increment quantity by 1
            current_quantity = int(response['Item'].get('quantity', 0))
            new_quantity = current_quantity + 1
            
            # Update the item with the new quantity
            table.update_item(
                Key={
                    'dealer_code': dealer_code,
                    'part_code': part_code
                },
                UpdateExpression="set quantity = :q",
                ExpressionAttributeValues={
                    ':q': new_quantity
                }
            )
            
            logger.info(f"Updated order quantity for dealer {dealer_code}, part {part_code} to {new_quantity}")
        else:
            # No existing order, create a new one with quantity 1
            table.put_item(
                Item={
                    'dealer_code': dealer_code,
                    'part_code': part_code,
                    'quantity': 1
                }
            )
            
            logger.info(f"Created new order for dealer {dealer_code}, part {part_code} with quantity 1")
        
        return "part order placed successfully"
            
    except ClientError as e:
        error_message = f"Error placing part order: {str(e)}"
        logger.error(error_message)
        return f"Failed to place part order: {str(e)}"
    except Exception as e:
        error_message = f"Unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return f"Failed to place part order: {str(e)}"
    except Exception as e:
        error_message = f"Unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return "0"  # Return 0 on error to allow workflow to continue

@tool
def delete_pending_orders(dealer_code: str, part_code: str = None) -> str:
    """
    Delete pending part orders from the Dealer_Parts_Order DynamoDB table.
    
    Use this tool to delete pending part orders for a specific dealer. If only dealer_code is provided,
    all orders for that dealer will be deleted. If both dealer_code and part_code are provided,
    only the specific order matching both keys will be deleted.
    
    Args:
        dealer_code: The dealer code for which to delete orders
                    Examples: "DLR123", "Jaguar Land Rover Seattle"
        part_code: Optional part code to delete a specific order
                  Examples: "393183L100", "3935037110"
    
    Returns:
        A string indicating the success or failure of the operation and the number of items deleted
    """
    try:
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table('Dealer_Parts_Order')
        
        deleted_count = 0
        
        if part_code:
            # Delete specific order matching both dealer_code and part_code
            response = table.delete_item(
                Key={
                    'dealer_code': dealer_code,
                    'part_code': part_code
                },
                ReturnValues='ALL_OLD'  # Return the deleted item
            )
            
            # Check if an item was actually deleted
            if 'Attributes' in response:
                deleted_count = 1
                logger.info(f"Deleted order for dealer {dealer_code}, part {part_code}")
                return f"Successfully deleted order for dealer {dealer_code}, part {part_code}"
            else:
                logger.info(f"No order found for dealer {dealer_code}, part {part_code}")
                return f"No order found for dealer {dealer_code}, part {part_code}"
        else:
            # Delete all orders for the dealer
            # First, query to get all items for this dealer
            response = table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('dealer_code').eq(dealer_code)
            )
            
            items = response.get('Items', [])
            
            # Delete each item individually
            for item in items:
                table.delete_item(
                    Key={
                        'dealer_code': dealer_code,
                        'part_code': item['part_code']
                    }
                )
                deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} orders for dealer {dealer_code}")
                return f"Successfully deleted {deleted_count} orders for dealer {dealer_code}"
            else:
                logger.info(f"No orders found for dealer {dealer_code}")
                return f"No orders found for dealer {dealer_code}"
            
    except ClientError as e:
        error_message = f"Error deleting orders: {str(e)}"
        logger.error(error_message)
        return f"Failed to delete orders: {str(e)}"
    except Exception as e:
        error_message = f"Unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return f"Failed to delete orders: {str(e)}"

class DynamoDBConversationManager:
    """Manages conversation history in DynamoDB."""

    def __init__(self, table_name: str, truncate_tools: bool = False):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.table_name = table_name
            self.truncate_tools = truncate_tools
            
            # Configure DynamoDB with retry configuration
            config = BotocoreConfig(
                region_name=REGION,
                retries={'max_attempts': 3, 'mode': 'adaptive'}
            )
            self.dynamodb = boto3.resource("dynamodb", config=config)
            self.table = self.dynamodb.Table(table_name)

    def add_user_message(self, session_id: str, user_query: str) -> None:
        """Add a user message to DynamoDB with current timestamp."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                item = {
                    "session_id": session_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": {"role": "user", "content": [{"text": user_query}]},
                    "ttl": int((datetime.now(timezone.utc).timestamp()) + (30 * 24 * 60 * 60))  # 30 days TTL
                }
                self.table.put_item(Item=item)
                logger.info(f"Added user message to session {session_id}")
            except Exception as e:
                logger.error(f"Error adding user message: {str(e)}")
                raise

    def add_agent_message(self, session_id: str, agent_message: Dict[str, Any]) -> None:
        """Add an agent message to DynamoDB with current timestamp."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                # Clean up tool results to reduce storage size (only if truncation is enabled)
                if self.truncate_tools and agent_message.get("content") and len(agent_message["content"]) > 0:
                    content_item = agent_message["content"][0]
                    if content_item.get("toolResult"):
                        # Keep tool results for memory tools, truncate others for storage efficiency
                        tool_name = content_item.get("toolUse", {}).get("name", "")
                        memory_tools = ["store_memory", "retrieve_memories", "list_memories"]
                        if tool_name not in memory_tools:
                            # Only truncate non-memory tool results
                            tool_content = content_item["toolResult"]["content"]
                            if isinstance(tool_content, list) and len(tool_content) > 0:
                                original_text = tool_content[0].get("text", "")
                                if len(original_text) > 500:  # Truncate long results
                                    truncated_text = f"{original_text[:500]}... [truncated]"
                                    content_item["toolResult"]["content"] = [{"text": truncated_text}]

                item = {
                    "session_id": session_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": agent_message,
                    "ttl": int((datetime.now(timezone.utc).timestamp()) + (30 * 24 * 60 * 60))  # 30 days TTL
                }
                self.table.put_item(Item=item)
                logger.info(f"Added agent message to session {session_id}")
            except Exception as e:
                logger.error(f"Error adding agent message: {str(e)}")
                # Don't raise here to avoid breaking the conversation flow
                pass

    def get_messages(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve messages for a session, sorted by timestamp with optional limit."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                response = self.table.query(
                    KeyConditionExpression="session_id = :sid",
                    ExpressionAttributeValues={":sid": session_id},
                    ScanIndexForward=True,  # Sort by timestamp ascending
                    Limit=limit
                )

                items = response.get("Items", [])
                if not items:
                    logger.info(f"No conversation history found for session {session_id}")
                    return []
                
                # Convert DynamoDB items and sort by timestamp
                dynamo_converted_items = [json_util.loads(item) for item in items]
                sorted_items = sorted(dynamo_converted_items, key=lambda x: x["timestamp"])

                logger.info(f"Retrieved {len(sorted_items)} messages for session {session_id}")
                return [item["message"] for item in sorted_items]

            except Exception as e:
                logger.error(f"Error retrieving messages from DynamoDB: {str(e)}")
                # Return empty list to allow conversation to continue
                return []

    def clear_history(self, session_id: str) -> int:
        """Clear all conversation history for a session. Returns count of deleted items."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                # First, get all items for the session
                response = self.table.query(
                    KeyConditionExpression="session_id = :sid", 
                    ExpressionAttributeValues={":sid": session_id}
                )

                items = response.get("Items", [])
                deleted_count = 0

                # Delete each item (DynamoDB doesn't support batch delete by query)
                for item in items:
                    self.table.delete_item(
                        Key={
                            "session_id": item["session_id"], 
                            "timestamp": item["timestamp"]
                        }
                    )
                    deleted_count += 1

                logger.info(f"Cleared {deleted_count} messages for session {session_id}")
                return deleted_count

            except Exception as e:
                logger.error(f"Error clearing history for session {session_id}: {str(e)}")
                raise
def wrapper_callback_handler(session_id, conversation_manager):

    def custom_callback_handler(**kwargs):
        # Process stream data
        if "data" in kwargs:
            print(f"MODEL OUTPUT: {kwargs['data']}")
        elif "current_tool_use" in kwargs and kwargs["current_tool_use"].get("name"):
            print(f"\nUSING TOOL: {kwargs['current_tool_use']['name']}")
        elif "message" in kwargs:
            conversation_manager.add_agent_message(session_id, kwargs["message"])
    
    return custom_callback_handler    

def handler(event: Dict[str, Any], _context) -> str:
    # Configuration constants
    DYNAMO_DB_CONVERSATION_HISTORY_TABLE = 'Strands_Conversation_History'  # Hardcoded table name
    CONVERSATION_MANAGER_WINDOW_SIZE = int(os.environ.get('CONVERSATION_WINDOW_SIZE', '10'))
    
    try:
        # Extract prompt and session_id from the event
        prompt = event.get('prompt')
        session_id = event.get('session_id', 'default-session')

        print ("ASA Agent Invoked")
        print ("Prompt: ", prompt)
        print ("Session ID: ", session_id)
        
        if not prompt:
            return json.dumps({"error": "Missing required parameter: prompt"})
        
        # Initialize DynamoDB conversation manager
        conversation_manager = DynamoDBConversationManager(
            table_name=DYNAMO_DB_CONVERSATION_HISTORY_TABLE,
            truncate_tools=False
        )
        
        # Get existing conversation history
        existing_messages = conversation_manager.get_messages(session_id)
        
        # Add current user message to history
        conversation_manager.add_user_message(session_id, prompt)
        
        # Create callback handler for this session
        callback_handler = wrapper_callback_handler(session_id, conversation_manager)

        bedrock_model = BedrockModel(
            model_id="eu.amazon.nova-pro-v1:0",
            region_name="eu-central-1",
            temperature=0.3,
            performance_config={"latency": "optimized"}
#            additionalModelRequestFields={"inferenceConfig": {"outputFilter": {"suppressedOutputTags": ["thinking"]}}}
        )
        
        # Initialize agent with conversation history
        agent = Agent(
            system_prompt=SYSTEM_PROMPT,
            model=bedrock_model,
            tools=[get_service_history, get_customer_vehicles, get_vehicle_recalls, 
                  search_service_manuals, get_parts_by_dtc, get_parts_by_name, get_appointments, 
                  get_pending_partorder, place_part_order, delete_pending_orders],
            messages=existing_messages,
            callback_handler=callback_handler
        )
        
        # Call the agent with the prompt
        response = agent(prompt)
        
        return str(response)
        
    except Exception as e:
        error_message = f"Error processing request: {str(e)}"
        logger.error(error_message)
        return json.dumps({"error": error_message})
