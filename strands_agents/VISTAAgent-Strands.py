from strands import Agent, tool
from typing import Dict, Any, List, Optional
import boto3
from botocore.exceptions import ClientError
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from boto3.dynamodb.conditions import Attr, Key
from dynamodb_json import json_util
from botocore.config import Config as BotocoreConfig
from strands.agent.conversation_manager import SlidingWindowConversationManager
from google.oauth2 import service_account
from googleapiclient.discovery import build
from zoneinfo import ZoneInfo
from strands.models import BedrockModel

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

#logging.getLogger("strands").setLevel(logging.DEBUG)
#logging.getLogger().setLevel(logging.DEBUG)
#logging.basicConfig(
#    level=logging.DEBUG,
#    format="%(levelname)s | %(name)s | %(message)s", 
#    handlers=[logging.StreamHandler()]
#)

# Set the region from environment variable
#REGION = 'eu-central-1'
REGION = 'eu-central-1'

SYSTEM_PROMPT = """You are a helpful VISTA (Vehicle Information System and Technical Assistant) agent for automotive customers.
You can help customers find the nearest authorized dealerships in a city, diagnose vehicle issues using VIN or customer ID and find service appointments.

IMPORTANT!!! Your output should always be in the JSON format as mentioned in the tool output. Please do not return any output that is NOT in JSON format and include all the data from the tool in the final output.

Finding a Dealer:

When a customer asks about finding a dealership use the tool find_nearest_dealerships:
IMPORTANT: Include all the dealer information that the tool returns in the final output.

1. Ask for their city if they haven't provided it
2. If you get a valid JSON response from the tool, just simply return that response including all the data. Do NOT add any other dealer information, and just pass the output from the tool find_nearest_dealerships.
3. Offer to help with any follow-up questions about the dealerships

Diagnose the vehicle:

When a customer asks about diagnosing vehicle issues use the tool diagnose_vehicle_issues and return the data in this format:

{ 
"message" : "Your vehicle has a trouble code P0340, which indicates a malfunction with the camshaft position sensor A circuit. This is rated as a high severity issue.\n
I strongly recommend booking a service appointment as soon as possible. Continuing to drive with this issue could potentially lead to further engine damage or leave you stranded.\n
Would you like me to help you find the nearest dealership where you can schedule a service appointment?\n"
}

Important: Keep your response short and sweet in less than 100 words.

1. Ask for their VIN or customer ID if they haven't provided it
2. Use the diagnose_vehicle_issues tool to retrieve diagnostic information
3. Explain the issue in simple terms, including the severity level as shortly as possible.
4. If the severity is high, strongly recommend booking a service appointment
5. If the severity is medium, suggest considering a service appointment
6. If the severity is low, inform them it's not urgent but should be addressed at their next service

Book an Appointment:

When a customer wants to book an appointment:
1. Ask for the dealer name, appointment date, appointment time, and customer code if they haven't provided them
2. Use the book_appointment tool to book the appointment
3. Return the confirmation message in JSON format:
{
  "message": "appointment successfully booked"
}
4. Do not add any additional text or formatting to the JSON response

Cancel an Appointment:

When a customer wants to cancel an appointment:
1. Ask for their customer code if they haven't provided it
2. Use the cancel_appointment tool to cancel all appointments for that customer
3. Return the confirmation message in JSON format:
{
  "message": "appointments canceled successfully"
}
4. Do not add any additional text or formatting to the JSON response

Find an Appointment:

When a customer asks about finding an appointment date and time use the tool find_appointment_slots by passing a dealer name and return the data in the following JSON format.
Include the information about calendar conflict if available:
{
  "dealer_name": "Crown Cars",
  "appointment_date": "2025-08-10",
  "appointment_time": "10:00 AM",
  "conflict": "yes",
  "conflicts_with": "Lunch with Lisa"
}

1. Ask for the dealer name and optionally a specific date.
2. If the date is in the past or on weekends, tell the user that you are not able to find appointments and ask for a new date. If the user did not provide a date, then search for the next weekday by adding one day.
3. Use the find_appointment_slots tool to find available appointment slots. The tool also checks for appointment conflicts with the customer's calendar.
4. Help them select a convenient time

Get customer Appointments:

When a customer asks about details of an already booked appointment then use this tool get_customer_appointments to get details of an appointment. Return the data in the following format.

{
  "dealer_name": "Crown Cars",
  "appointment_date": "2025-08-10",
  "appointment_time": "10:00 AM",
  "customer_code": "JSmith"
}

Be friendly, concise, and helpful in your responses. If you don't have information about a particular topic,
let the customer know and suggest alternative ways they might find that information.

Always just return the JSON array No other text or formatting.

"""

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)

def get_google_calendar_service(read_only=True):
    """
    Initialize Google Calendar service using credentials from AWS Secrets Manager.
    
    Args:
        read_only: If True, uses readonly scope. If False, uses full calendar scope.
    """
    try:
        # Get credentials from AWS Secrets Manager
        secrets_client = boto3.client('secretsmanager', region_name=REGION)
        secret_response = secrets_client.get_secret_value(SecretId='prod/google')
        credentials_json = json.loads(secret_response['SecretString'])
        
        # Create credentials from the JSON with appropriate scope
        if read_only:
            SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
        else:
            SCOPES = ['https://www.googleapis.com/auth/calendar']
        
        credentials = service_account.Credentials.from_service_account_info(
            credentials_json, scopes=SCOPES
        )
        
        # Build and return the service
        service = build('calendar', 'v3', credentials=credentials)
        return service
        
    except Exception as e:
        logger.error(f"Failed to initialize Google Calendar service: {str(e)}")
        return None

def check_calendar_conflicts(appointment_slots):
    """
    Check Google Calendar for conflicts with appointment slots.
    
    Args:
        appointment_slots: List of appointment slot dictionaries with date and time
    
    Returns:
        List of appointment slots with conflict information added
    """
    try:
        service = get_google_calendar_service()
        if not service:
            logger.warning("Google Calendar service not available, skipping conflict check")
            return appointment_slots
        
        calendar_id = 'youremail@gmail.com'
        
        # Get the next 10 events from Google Calendar
        events_result = service.events().list(
            calendarId=calendar_id, 
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])

        for event in events:
            print(event)
        
        # Check each appointment slot for conflicts
        enhanced_slots = []
        for slot in appointment_slots:
            slot_date = slot['appointment_date']
            slot_time = slot['appointment_time']
            
            # Convert appointment slot to datetime for comparison
            slot_datetime = datetime.strptime(f"{slot_date} {slot_time}", "%Y-%m-%d %I:%M %p")
            slot_end_datetime = slot_datetime + timedelta(hours=1)  # Assume 1-hour appointments
            
            # Check for conflicts with calendar events
            conflict_found = False
            conflict_event = None
            
            for event in events:
                # Parse event start and end times
                event_start_str = event['start'].get('dateTime', event['start'].get('date'))
                event_end_str = event['end'].get('dateTime', event['end'].get('date'))
                
                # Handle different date formats
                try:
                    if 'T' in event_start_str:
                        # DateTime format
                        event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00')).replace(tzinfo=None)
                        event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00')).replace(tzinfo=None)
                    else:
                        # Date-only format (all-day events)
                        event_start = datetime.strptime(event_start_str, "%Y-%m-%d")
                        event_end = datetime.strptime(event_end_str, "%Y-%m-%d")
                    
                    # Check for overlap
                    if (slot_datetime < event_end and slot_end_datetime > event_start):
                        conflict_found = True
                        conflict_event = {
                            'summary': event.get('summary', 'No title'),
                            'start': event['start'],
                            'end': event['end']
                        }
                        break
                        
                except Exception as e:
                    logger.warning(f"Error parsing event time: {str(e)}")
                    continue
            
            # Add conflict information to the slot
            enhanced_slot = slot.copy()
            if conflict_found:
                enhanced_slot['conflict'] = 'yes'
                enhanced_slot['conflicts_with'] = conflict_event['summary']
            else:
                enhanced_slot['conflict'] = 'no'
            
            enhanced_slots.append(enhanced_slot)
        
        return enhanced_slots
        
    except Exception as e:
        logger.error(f"Error checking calendar conflicts: {str(e)}")
        # Return original slots without conflict information if calendar check fails
        for slot in appointment_slots:
            slot['conflict'] = 'no'
        return appointment_slots

def create_calendar_event(dealer_name, appointment_date, appointment_time):
    """
    Create a Google Calendar event for the booked appointment.
    
    Args:
        dealer_name: Name of the dealer
        appointment_date: Date in YYYY-MM-DD format
        appointment_time: Time in HH:MM AM/PM format
    
    Returns:
        True if event created successfully, False otherwise
    """
    try:
        service = get_google_calendar_service(read_only=False)
        if not service:
            logger.warning("Google Calendar service not available, skipping event creation")
            return False
        
        calendar_id = 'youremail@gmail.com'
        
        # Parse appointment date and time
        appointment_datetime = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %I:%M %p")
        central_tz = ZoneInfo("America/Chicago")
        appointment_datetime = appointment_datetime.replace(tzinfo=central_tz)
        
        end_datetime = appointment_datetime + timedelta(hours=1)  # 1-hour appointment
        
        # Format times for Google Calendar API (ISO format)
        start_time_str = appointment_datetime.isoformat()
        end_time_str = end_datetime.isoformat()
        
        # Create event body
        event_body = {
            'summary': f'Appointment with {dealer_name}',
            'description': f'Appointment with {dealer_name}',
            'start': {
                'dateTime': start_time_str,
                'timeZone': 'America/Los_Angeles',
            },
            'end': {
                'dateTime': end_time_str,
                'timeZone': 'America/Los_Angeles',
            },
        }
        
        # Create the event
        created_event = service.events().insert(
            calendarId=calendar_id, 
            body=event_body, 
            sendNotifications=False
        ).execute()
        
        logger.info(f"Calendar event created successfully: {created_event['id']}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating calendar event: {str(e)}")
        return False

def delete_calendar_events_by_appointment(dealer_name, appointment_date, appointment_time):
    """
    Delete Google Calendar events that match the appointment details.
    
    Args:
        dealer_name: Name of the dealer
        appointment_date: Date in YYYY-MM-DD format  
        appointment_time: Time in HH:MM AM/PM format
    
    Returns:
        Number of events deleted
    """
    try:
        service = get_google_calendar_service(read_only=False)
        if not service:
            logger.warning("Google Calendar service not available, skipping event deletion")
            return 0
        
        calendar_id = 'youremail@gmail.com'
        
        # Parse appointment date and time with timezone awareness
        appointment_datetime = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %I:%M %p")
        central_tz = ZoneInfo("America/Chicago")
        appointment_datetime = appointment_datetime.replace(tzinfo=central_tz)
        
        # Search for events on the appointment date
        start_of_day = appointment_date + "T00:00:00-08:00"  
        end_of_day = appointment_date + "T23:59:59-08:00"    
        
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_of_day,
            timeMax=end_of_day,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        deleted_count = 0
        
        # Look for events that match our appointment
        for event in events:
            event_summary = event.get('summary', '')
            
            # Check if this event matches our appointment
            if f'Appointment with {dealer_name}' in event_summary:
                # Additional time check to make sure it's the right appointment
                event_start_str = event['start'].get('dateTime', event['start'].get('date'))
                
                try:
                    if 'T' in event_start_str:
                        # Parse the event time with timezone awareness
                        event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00'))
                        
                        # Convert to Central timezone for comparison
                        if event_start.tzinfo is None:
                            event_start = event_start.replace(tzinfo=central_tz)
                        else:
                            event_start = event_start.astimezone(central_tz)
                        
                        # Check if the times match (within 1 minute tolerance)
                        time_diff = abs((event_start - appointment_datetime).total_seconds())
                        
                        if time_diff <= 60:  # Within 1 minute
                            # Delete the event
                            service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()
                            logger.info(f"Deleted calendar event: {event['id']} for {dealer_name} at {appointment_time}")
                            deleted_count += 1
                            
                except Exception as e:
                    logger.warning(f"Error parsing event time for deletion: {str(e)}")
                    continue
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error deleting calendar events: {str(e)}")
        return 0

def normalize_country_name(query_term):
    """Normalize country names to match database format"""
    country_mapping = {
        "germany": "Germany",
        "usa": "USA", 
        "united states": "USA",
        "america": "USA",
        "us": "USA"
    }
    return country_mapping.get(query_term.lower(), query_term.title())

def is_country_query(query_term):
    """Check if the query term might be a country name"""
    countries = ["germany", "usa", "united states", "america", "us"]
    return query_term.lower() in countries

@tool
def find_nearest_dealerships(city: str, customer_id: str = None) -> str:
    """
    Find dealerships in a specific city, with optional preferred dealer check.
    
    This tool queries the dealership database to find authorized dealerships located in the specified city.
    If a customer_id is provided, it also checks if any of the dealerships are marked as preferred
    by that customer. Consider the response of the tool as the complete list of Authorized dealerships.
    
    Args:
        city: The name of the city to search for dealerships
              Examples: "Seattle", "San Francisco", "New York"
        customer_id: Optional customer ID to check for preferred dealers
                    Examples: "CUST123", "C-98765"
    
    Returns:
        A JSON string containing information about authorized dealerships in the specified city,
        with preferred dealer indicators if applicable
    """
    try:
        # Normalize the city name to match stored format (e.g., "San Francisco")
        city = city.title()
        
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        dealer_table = dynamodb.Table('Dealer_Data') 
        
        # First try querying by city (efficient hash key lookup)
        response = dealer_table.query(
            KeyConditionExpression=Key("city").eq(city)
        )
        
        # Check if any dealerships were found
        items = response.get("Items", [])
        
        # If no results and might be a country query, try country search
        if not items and is_country_query(city):
            logger.info(f"No dealerships found in city {city}, trying country-based search")
            normalized_country = normalize_country_name(city)
            response = dealer_table.scan(
                FilterExpression=Attr("country").eq(normalized_country)
            )
            items = response.get("Items", [])
        
        # Check if any dealerships were found after both searches
        if not items:
            if is_country_query(city):
                return json.dumps({
                    "message": f"No dealerships found in {normalize_country_name(city)}",
                    "total_count": 0,
                    "is_complete": True
                })
            else:
                return json.dumps({
                    "message": f"No dealerships found in {city}. Try searching by country if looking internationally.",
                    "total_count": 0,
                    "is_complete": True
                })
        
        # Process and format the dealership information
        dealerships = []
        
        # If customer_id is provided, check for preferred dealer
        preferred_dealer_name = None
        if customer_id:
            try:
                # Query Customer_Data table for preferred dealer
                customer_table = dynamodb.Table('Customer_Data')
                customer_response = customer_table.query(
                    KeyConditionExpression=boto3.dynamodb.conditions.Key('CustomerID').eq(customer_id)
                )
                
                if 'Items' in customer_response and customer_response['Items']:
                    # Get the preferred dealer from the first item
                    preferred_dealer_name = customer_response['Items'][0].get('PreferredDealer')
                    logger.info(f"Found preferred dealer for customer {customer_id}: {preferred_dealer_name}")
            except Exception as e:
                logger.error(f"Error querying for preferred dealer: {str(e)}")
                # Continue execution even if preferred dealer lookup fails
        
        for item in items:
            dealership = {
                "dealer_name": item.get("dealer_name"),
                "preferred_dealer": "Yes" if preferred_dealer_name and item.get("dealer_name") == preferred_dealer_name else "No",
                "city": item.get("city"),
                "website": item.get("website"),
                "street": item.get("street"),
                "state": item.get("state"),
                "country": item.get("country"),
                "zip": item.get("zip"),
                "phone": item.get("phone"),
                "email": item.get("email")
            }
            
            dealerships.append(dealership)
        
        print(dealerships)
        # Return the dealership information as a JSON string
        return json.dumps({
            "dealerships": dealerships,
            "total_count": len(dealerships),
            "is_complete": True
        }, cls=DecimalEncoder)
        
    except ClientError as e:
        error_message = f"Error querying DynamoDB: {str(e)}"
        logger.error(error_message)
        return json.dumps({"error": error_message, "is_complete": True})
    except Exception as e:
        error_message = f"Unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return json.dumps({"error": error_message, "is_complete": True})

@tool
def diagnose_vehicle_issues(customer_id: str = None, vin: str = None) -> str:
    """
    Diagnose vehicle issues using either a customer ID or VIN.
    
    This tool queries the Customer_Data DynamoDB table to retrieve diagnostic trouble codes (DTCs)
    and related information for a specific vehicle. It can search by either customer ID or VIN.
    The tool returns detailed information about any active DTCs, including code, description,
    severity, and a conversational response explaining the issue.
    
    Args:
        customer_id: The customer's ID to search for vehicle issues (optional if VIN provided)
                    Examples: "CUST123", "C-98765"
        vin: The Vehicle Identification Number to search for issues (optional if customer_id provided)
             Examples: "1HGCV1F34NA123456", "WBADT43483G473298"
    
    Returns:
        A JSON string containing diagnostic information about the vehicle,
        including DTC codes, descriptions, severity levels, and a conversational response
    """
    try:
        # Validate input - must have either customer_id or vin
        if not customer_id and not vin:
            return json.dumps({
                "error": "Either customer_id or vin parameter is required for diagnosis",
                "is_complete": True
            })
        
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table('Customer_Data')
        
        dtc_results = []
        
        if customer_id:
            # Query by CustomerID (efficient - uses partition key)
            logger.info(f"Querying by CustomerID: {customer_id}")
            
            response = table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('CustomerID').eq(customer_id)
            )
            
            if 'Items' in response and response['Items']:
                for item in response['Items']:
                    if item.get('ActiveDTCCode') and item.get('DTCDescription'):
                        # Get severity directly from DynamoDB table
                        severity = item.get('Severity', 'unknown')
                        
                        dtc_info = {
                            'CustomerID': item.get('CustomerID'),
                            'VehicleID': item.get('VehicleID'),
                            'Make': item.get('Make'),
                            'Model': item.get('Model'),
                            'ModelYear': item.get('ModelYear'),
                            'ActiveDTCCode': item.get('ActiveDTCCode'),
                            'DTCDescription': item.get('DTCDescription'),
                            'Severity': severity
                        }
                        dtc_results.append(dtc_info)
            
        elif vin:
            # Scan by VIN (less efficient - scans entire table)
            logger.info(f"Scanning by VIN: {vin}")
            
            response = table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('VehicleID').eq(vin)
            )
            
            if 'Items' in response and response['Items']:
                for item in response['Items']:
                    if item.get('ActiveDTCCode') and item.get('DTCDescription'):
                        # Get severity directly from DynamoDB table
                        severity = item.get('Severity', 'unknown')
                        
                        dtc_info = {
                            'CustomerID': item.get('CustomerID'),
                            'VehicleID': item.get('VehicleID'),
                            'Make': item.get('Make'),
                            'Model': item.get('Model'),
                            'ModelYear': item.get('ModelYear'),
                            'ActiveDTCCode': item.get('ActiveDTCCode'),
                            'DTCDescription': item.get('DTCDescription'),
                            'Severity': severity
                        }
                        dtc_results.append(dtc_info)
        
        # Format and return results
        if dtc_results:
            return json.dumps({
                "diagnosis_results": dtc_results,
                "total_count": len(dtc_results),
                "is_complete": True
            }, cls=DecimalEncoder)
        else:
            search_term = customer_id if customer_id else vin
            search_type = 'CustomerID' if customer_id else 'VIN'
            return json.dumps({
                "message": f"No active DTC codes found for {search_type}: {search_term}",
                "is_complete": True
            })
            
    except ClientError as e:
        error_message = f"Error querying DynamoDB: {str(e)}"
        logger.error(error_message)
        return json.dumps({"error": error_message, "is_complete": True})
    except Exception as e:
        error_message = f"Unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return json.dumps({"error": error_message, "is_complete": True})

@tool
def find_appointment_slots(dealer_name: str, appointment_date: str = None) -> str:
    """
    Find available appointment slots for a specific dealer.
    
    This tool queries the Dealer_Appointment_Data DynamoDB table to find available
    appointment slots for a specified dealer. If an appointment date is provided,
    it returns available slots for that date. Otherwise, it returns the next 5
    available slots across multiple days.
    
    Args:
        dealer_name: The name of the dealer to search for appointment slots
                    Examples: "Crown Cars", "Apex Autos"
        appointment_date: Optional specific date to search for appointments in YYYY-MM-DD format
                         Examples: "2025-07-20", "2025-08-15"
    
    Returns:
        A JSON string containing available appointment slots with dealer name, date, and time
    """
    try:
        # Define available time slots (hourly from 8 AM to 5 PM)
        AVAILABLE_SLOTS = [
            "08:00 AM", "09:00 AM", "10:00 AM", "11:00 AM", 
            "12:00 PM", "01:00 PM", "02:00 PM", "03:00 PM", 
            "04:00 PM", "05:00 PM"
        ]
        
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        appointment_table = dynamodb.Table('Dealer_Appointment_Data')
        
        # Early validation for appointment date if provided
        if appointment_date:
            # Check if appointment date is a Sunday (dealers are open on Saturdays)
            appointment_date_obj = datetime.strptime(appointment_date, "%Y-%m-%d")
            if appointment_date_obj.weekday() == 6:  # 6 = Sunday
                return json.dumps({
                    "error": f"The dealer is closed on Sundays. Please select another day (Monday to Saturday)."
                })
            
            # Check if appointment date is today or in the past
            today = datetime.now().strftime("%Y-%m-%d")
            if appointment_date <= today:
                return json.dumps({
                    "error": "We cannot find appointment slots for today or past dates."
                })
        
        # Helper functions
        def get_next_business_day(start_date=None):
            """Get the next business day from the given start_date (or today +1 if None), skipping Sundays."""
            if start_date:
                next_day = datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=1)
            else:
                next_day = datetime.now() + timedelta(days=1)

            # Skip only Sundays (weekday 6), as dealers are open on Saturdays
            while next_day.weekday() == 6:  # 6 = Sunday
                next_day += timedelta(days=1)
            
            return next_day.strftime("%Y-%m-%d")
        
        def format_dealer_name(dealer_name):
            """Format dealer name with first letter of each word capitalized."""
            if not dealer_name:
                return dealer_name
            # Split by spaces and capitalize first letter of each word
            words = dealer_name.split()
            formatted_name = ' '.join(word.capitalize() for word in words)
            return formatted_name
        
        def get_booked_appointments(dealer_name, appointment_date, appointment_table):
            """Scan DynamoDB to get booked appointments for a given dealer name and date."""
            # Format dealer name to match the format in DynamoDB
            formatted_dealer_name = format_dealer_name(dealer_name)
            
            response = appointment_table.scan(
                FilterExpression=Attr("dealer_name").eq(formatted_dealer_name) & 
                                Attr("appointment_date_time").begins_with(appointment_date)
            )

            return {item["appointment_date_time"][11:] for item in response.get("Items", [])}
        
        def find_available_slots_for_date(dealer_name, appointment_date, appointment_table):
            """Find available appointment slots for a specific date."""
            booked_slots = get_booked_appointments(dealer_name, appointment_date, appointment_table)
            
            # Find slots that are not booked for the specified date
            available_slots = [
                (appointment_date, slot) for slot in AVAILABLE_SLOTS 
                if slot not in booked_slots
            ]
            
            # Return available slots for the requested date (may be empty)
            return available_slots
        
        def find_available_slots(dealer_name, appointment_table):
            """Find 5 available appointment slots, searching across multiple days if needed."""
            slots_found = []
            search_date = get_next_business_day()
            
            while len(slots_found) < 5:
                booked_slots = get_booked_appointments(dealer_name, search_date, appointment_table)
                
                # Find slots that are not booked
                available_slots = [
                    (search_date, slot) for slot in AVAILABLE_SLOTS 
                    if slot not in booked_slots
                ]
                
                if available_slots:
                    slots_needed = 5 - len(slots_found)
                    slots_found.extend(available_slots[:slots_needed])

                # Move to the next business day if we haven't found enough slots
                if len(slots_found) < 5:
                    search_date = get_next_business_day(search_date)

            return slots_found
        
        def get_dealer_details(dealer_name):
            """Get dealer details from the Dealer_Data table."""
            dealer_table = dynamodb.Table("Dealer_Data")
            
            # Format dealer name to match the format in DynamoDB
            formatted_dealer_name = format_dealer_name(dealer_name)
            
            response = dealer_table.scan(
                FilterExpression=Attr("dealer_name").eq(formatted_dealer_name)
            )
            
            items = response.get("Items", [])
            if not items:
                return None
            
            return items[0].get("dealer_name")
        
        # Get dealer details
        formatted_dealer_name = get_dealer_details(dealer_name)
        if not formatted_dealer_name:
            return json.dumps({
                "error": f"We could not find a dealer with the name '{dealer_name}'. Please check the dealer name and try again."
            })
        
        # Find available slots based on whether a specific date was provided
        if appointment_date:
            available_slots = find_available_slots_for_date(dealer_name, appointment_date, appointment_table)
            if not available_slots:
                # Format the date for display (assuming appointment_date is in YYYY-MM-DD format)
                formatted_date = datetime.strptime(appointment_date, "%Y-%m-%d").strftime("%m-%d-%Y")
                return json.dumps({
                    "error": f"There are no available slots for the date {formatted_date}"
                })
        else:
            available_slots = find_available_slots(dealer_name, appointment_table)
        
        # Create simplified output format - just an array of objects with dealer name, date and time
        simplified_slots = []
        for date, time in available_slots:
            simplified_slots.append({
                "dealer_name": formatted_dealer_name,
                "appointment_date": date,
                "appointment_time": time
            })
        
        # Check for Google Calendar conflicts before returning
        enhanced_slots = check_calendar_conflicts(simplified_slots)
        
        # Return the enhanced slots with conflict information
        return json.dumps(enhanced_slots, cls=DecimalEncoder)
        
    except ClientError as e:
        error_message = f"Error querying DynamoDB: {str(e)}"
        logger.error(error_message)
        return json.dumps({"error": error_message})
    except Exception as e:
        error_message = f"Unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return json.dumps({"error": error_message})

@tool
def cancel_appointment(customer_code: str) -> str:
    """
    Cancel all appointments for a specific customer.
    
    This tool deletes all appointments for the specified customer from the
    Dealer_Appointment_Data DynamoDB table.
    
    Args:
        customer_code: The customer's unique identifier
                      Examples: "CUST123", "C-98765"
    
    Returns:
        A JSON string indicating whether the appointments were successfully canceled
    """
    try:
        # Validate required parameter
        if not customer_code:
            return json.dumps({
                "error": "Missing customer code"
            })
        
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table('Dealer_Appointment_Data')
        
        # Find all appointments for this customer
        response = table.scan(
            FilterExpression=Attr('customer_code').eq(customer_code)
        )
        
        # If no appointments found, return message
        if 'Items' not in response or len(response['Items']) == 0:
            return json.dumps({
                "error": "No appointments found for this customer"
            })
        
        # Delete all appointments found and corresponding calendar events
        deleted_count = 0
        calendar_deleted_count = 0
        
        for item in response['Items']:
            # Delete from DynamoDB
            if 'dealer_name' in item and 'appointment_date_time' in item:
                table.delete_item(
                    Key={
                        'dealer_name': item['dealer_name'],
                        'appointment_date_time': item['appointment_date_time']
                    }
                )
                deleted_count += 1
                
                # Delete corresponding Google Calendar event
                try:
                    appointment_parts = item['appointment_date_time'].split(' ', 1)
                    if len(appointment_parts) == 2:
                        appt_date = appointment_parts[0]  # YYYY-MM-DD
                        appt_time = appointment_parts[1]  # HH:MM AM/PM
                        
                        deleted_events = delete_calendar_events_by_appointment(
                            item['dealer_name'], 
                            appt_date, 
                            appt_time
                        )
                        calendar_deleted_count += deleted_events
                        
                except Exception as calendar_error:
                    logger.error(f"Error deleting calendar event: {str(calendar_error)}")
        
        if calendar_deleted_count > 0:
            logger.info(f"Deleted {calendar_deleted_count} calendar events")
        
        # Return success message
        return json.dumps({
            "message": "appointments canceled successfully",
            "appointments_deleted": deleted_count,
            "calendar_events_deleted": calendar_deleted_count
        })
        
    except ClientError as e:
        error_message = f"Error canceling appointment: {str(e)}"
        logger.error(error_message)
        return json.dumps({"error": error_message})
    except Exception as e:
        error_message = f"Unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return json.dumps({"error": error_message})

@tool
def book_appointment(dealer_name: str, appointment_date: str, appointment_time: str, customer_code: str) -> str:
    """
    Book an appointment with a dealer.
    
    This tool books an appointment with a specified dealer at a given date and time.
    It stores the appointment in the Dealer_Appointment_Data DynamoDB table and
    sends a confirmation email to the customer if their email is available.
    
    Args:
        dealer_name: The name of the dealer to book an appointment with
                    Examples: "Crown Cars", "Apex Autos"
        appointment_date: The date for the appointment in YYYY-MM-DD format
                         Examples: "2025-07-20", "2025-08-15"
        appointment_time: The time for the appointment in HH:MM AM/PM format
                         Examples: "10:00 AM", "02:30 PM"
        customer_code: The customer's unique identifier
                      Examples: "CUST123", "C-98765"
    
    Returns:
        A JSON string indicating whether the appointment was successfully booked
    """
    try:
        # Validate required parameters
        if not dealer_name or not appointment_date or not appointment_time or not customer_code:
            return json.dumps({
                "error": "Missing dealer name, appointment date, customer code or appointment time"
            })
        
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table('Dealer_Appointment_Data')
        
        appointment_date_time = f"{appointment_date} {appointment_time}"
        
        # Check if customer already has any appointment
        response = table.scan(
            FilterExpression=Attr('customer_code').eq(customer_code)
        )
        
        # If customer already has an appointment, return error message
        if 'Items' in response and len(response['Items']) > 0:
            return json.dumps({
                "error": "Customer already has an existing appointment"
            })
        
        # If no existing appointment, proceed with creating new one
        item = {
            "dealer_name": dealer_name,
            "appointment_date_time": appointment_date_time,
            "customer_code": customer_code,
            "technician_code": "TECH001"
        }
        
        table.put_item(Item=item)
        
        # Look up customer email
        #customer_id_title = customer_code.title()
        customer_table = dynamodb.Table("Customer_Data")
        
        logger.info(f"querying customer table to get email ID {customer_code}")
        
        # Variables for email
        customer_email = None
        formatted_date = appointment_date
        formatted_time = appointment_time
        
        try:
            # Query by CustomerID (using the correct partition key name)
            customer_response = customer_table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('CustomerID').eq(customer_code)
            )
            
            # Check if Items exists and has at least one item with email
            if 'Items' in customer_response and len(customer_response['Items']) > 0:
                # Get the first matching customer record
                customer_item = customer_response['Items'][0]
                if 'email' in customer_item:
                    customer_email = customer_item['email']
                    
                    try:
                        appointment_dt = datetime.strptime(appointment_date_time, "%Y-%m-%d %H:%M %p")
                        formatted_date = appointment_dt.strftime("%A, %B %d, %Y")
                        formatted_time = appointment_dt.strftime("%I:%M %p")
                    except Exception as format_error:
                        logger.error(f"Error formatting date/time: {str(format_error)}")
                        # Use the original values if formatting fails
                        formatted_date = appointment_date
                        formatted_time = appointment_time
        except Exception as query_error:
            logger.error(f"Error querying customer data: {str(query_error)}")
            # Continue with booking even if customer lookup fails
        
        # Send email if we found a customer email
        if customer_email:
            email_subject = f"Your Appointment Confirmation with {dealer_name}"
            email_body = f"""
            <html>
            <body>
                <h2>Your Appointment Has Been Booked</h2>
                <p>Dear Customer,</p>
                <p>Your appointment with {dealer_name} has been successfully booked.</p>
                <p><strong>Appointment Details:</strong></p>
                <ul>
                    <li>Date: {formatted_date}</li>
                    <li>Time: {formatted_time}</li>
                    <li>Dealer: {dealer_name}</li>
                    <li>Confirmation Code: {customer_code}</li>
                </ul>
                <p>If you need to reschedule or cancel your appointment, please contact us.</p>
                <p>Thank you for choosing our service!</p>
            </body>
            </html>
            """
            
            # Send email using SES
            try:
                ses_client = boto3.client('ses', region_name=REGION)
                ses_client.send_email(
                    Source='vedev@amazon.com',  # Replace with your verified email
                    Destination={
                        'ToAddresses': [customer_email]
                    },
                    Message={
                        'Subject': {
                            'Data': email_subject
                        },
                        'Body': {
                            'Html': {
                                'Data': email_body
                            }
                        }
                    }
                )
                logger.info(f"Confirmation email sent to {customer_email}")
            except Exception as email_error:
                logger.error(f"Error sending email: {str(email_error)}")
        
        # Create Google Calendar event for the appointment
        try:
            calendar_success = create_calendar_event(dealer_name, appointment_date, appointment_time)
            if calendar_success:
                logger.info(f"Calendar event created for appointment with {dealer_name}")
            else:
                logger.warning(f"Failed to create calendar event for appointment with {dealer_name}")
        except Exception as calendar_error:
            logger.error(f"Error creating calendar event: {str(calendar_error)}")
        
        # Return success message
        return json.dumps({
            "message": "appointment successfully booked"
        })
        
    except ClientError as e:
        error_message = f"Error booking appointment: {str(e)}"
        logger.error(error_message)
        return json.dumps({"error": error_message})
    except Exception as e:
        error_message = f"Unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return json.dumps({"error": error_message})

@tool
def get_customer_appointments(customer_code: str) -> str:
    """
    Get current and future appointments for a specific customer from the Dealer_Appointment_Data table.
    Only returns appointments from today onwards, excluding past appointments.
    
    Args:
        customer_code (str): The customer code to search for appointments
        
    Returns:
        str: JSON string containing appointment details or error message
    """
    try:
        # Create DynamoDB resource
        dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
        table = dynamodb.Table('Dealer_Appointment_Data')
        
        # Get current date and time
        current_datetime = datetime.now()
        
        # Scan the table filtering by customer_code
        response = table.scan(
            FilterExpression=Attr('customer_code').eq(customer_code)
        )
        
        appointments = []
        for item in response['Items']:
            appointment_date_time_str = item.get('appointment_date_time', '')
            
            try:
                # Parse the appointment datetime (format: "YYYY-MM-DD HH:MM AM/PM")
                appointment_datetime = datetime.strptime(appointment_date_time_str, "%Y-%m-%d %I:%M %p")
                
                # Only include appointments from today onwards
                if appointment_datetime.date() >= current_datetime.date():
                    # Split the appointment_date_time to get separate date and time
                    date_part, time_part = appointment_date_time_str.split(' ', 1)
                    
                    appointment = {
                        'dealer_name': item.get('dealer_name', 'N/A'),
                        'appointment_date': date_part,
                        'appointment_time': time_part,
                        'customer_code': item.get('customer_code', 'N/A')
                    }
                    appointments.append(appointment)
                    
            except ValueError as e:
                logger.warning(f"Could not parse appointment datetime '{appointment_date_time_str}': {str(e)}")
                continue
        
        if not appointments:
            return json.dumps({
                "status": "success",
                "message": f"No current or future appointments found for customer code: {customer_code}",
                "appointments": []
            })
        
        # Sort appointments by date and time
        appointments.sort(key=lambda x: datetime.strptime(f"{x['appointment_date']} {x['appointment_time']}", "%Y-%m-%d %I:%M %p"))
        
        return json.dumps({
            "status": "success",
            "message": f"Found {len(appointments)} current/future appointment(s) for customer code: {customer_code}",
            "appointments": appointments
        })
        
    except Exception as e:
        logger.error(f"Error retrieving customer appointments: {str(e)}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to retrieve appointments: {str(e)}"
        })

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

        print("VISTA Agent Invoked")
        print("Event: ", event)
        print("Prompt: ", prompt)
        print("Session ID: ", session_id)
        
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
        )
        
        # Initialize agent with conversation history
        agent = Agent(
            model=bedrock_model,
            system_prompt=SYSTEM_PROMPT,
            tools=[find_nearest_dealerships, diagnose_vehicle_issues, find_appointment_slots, book_appointment, cancel_appointment, get_customer_appointments],
            messages=existing_messages,
            callback_handler=callback_handler
        )
        print(agent.model.config)

        # Call the agent with the prompt
        response = agent(prompt)
        
        return str(response)
        
    except Exception as e:
        error_message = f"Error processing request: {str(e)}"
        logger.error(error_message)
        return json.dumps({"error": error_message})
